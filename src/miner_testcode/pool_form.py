"""Real AxeOS pool-form interactions with a guarded device write boundary."""
from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

from .errors import DeviceError
from .pool_fallback import PoolDashboard, TemporaryPools


def guarded_form_payload(payload: Any, pools: TemporaryPools) -> dict[str, Any]:
    """Preserve submitted edits/roles, excluding untouched originals and passwords.

    The real form submits every pool, including masked passwords. Only owned
    disposable entries may cross the hardware write boundary. Reject unexpected
    edits instead of silently correcting them to the expected test result.
    """
    if not isinstance(payload, dict) or set(payload) != {
        'pools', 'primaryPoolIndex', 'secondaryPoolIndex'
    }:
        raise DeviceError('unexpected browser pool-form fields')
    primary, secondary = payload['primaryPoolIndex'], payload['secondaryPoolIndex']
    if (type(primary) is not int or type(secondary) is not int or
            primary not in pools.owned or secondary not in pools.owned or primary == secondary):
        raise DeviceError('browser selected invalid or unowned pool roles')
    rows = payload['pools']
    if not isinstance(rows, list) or len(rows) > 8:
        raise DeviceError('invalid browser pool table')
    seen: set[int] = set()
    safe_rows = []
    for row in rows:
        if not isinstance(row, dict) or type(row.get('id')) is not int or row['id'] in seen:
            raise DeviceError('invalid or duplicate browser pool ID')
        index = row['id']
        seen.add(index)
        if index in pools.original:
            original = pools.original[index]
            for key, value in row.items():
                if key == 'stratumPassword' and value in ('', '*****'):
                    continue
                if key in original and value != original[key]:
                    raise DeviceError('browser attempted to edit an original pool')
            continue
        if index not in pools.owned:
            raise DeviceError('browser attempted to add an unowned pool')
        entry = pools.entries[index]
        if not set(entry).issubset(row):
            raise DeviceError('browser omitted temporary pool fields')
        for key, value in entry.items():
            if key != 'stratumUser' and row[key] != value:
                raise DeviceError('unexpected temporary pool change from browser')
        user = row['stratumUser']
        if (not isinstance(user, str) or not user.startswith('fallback-regression.') or
                len(user) > 128 or any(part in user for part in ('*', '<', '>', '${'))):
            raise DeviceError('browser submitted an invalid disposable worker')
        if row.get('stratumPassword') not in (None, '', '*****'):
            raise DeviceError('browser password edits are outside this scenario')
        # Passwords and unused protocol defaults are omitted, never substituted.
        safe_rows.append({key: row[key] for key in entry})
    if seen != set(pools.original) | pools.owned:
        raise DeviceError('browser omitted or added pool entries')
    return {'primaryPoolIndex': primary, 'secondaryPoolIndex': secondary, 'pools': safe_rows}


class PoolSettingsForm(PoolDashboard):
    """A separate CDP session handles paused requests while commands are pending."""
    def __init__(self, endpoint: str, device_url: str, pools: TemporaryPools) -> None:
        super().__init__(endpoint, device_url)
        self.pools = pools
        self.reader: asyncio.Task | None = None
        self.pending: dict[int, asyncio.Future] = {}
        self.acknowledgements: set[int] = set()
        self.failure: Exception | None = None
        self.saved_count = 0
        self.request_count = 0

    async def _connected(self) -> None:
        self.reader = asyncio.create_task(self._read(), name='pool-form-cdp')

    async def start(self) -> None:
        await super().start()
        await self.command('Fetch.enable', {'patterns': [
            {'urlPattern': self.device_url + '/api/*', 'requestStage': 'Request'}
        ]})

    async def command(self, method: str, params: dict | None = None) -> Any:
        if self.failure:
            raise self.failure
        if self.socket is None or len(self.pending) >= 8:
            raise DeviceError('browser is unavailable or has too many pending commands')
        self.sequence += 1
        ident = self.sequence
        future = asyncio.get_running_loop().create_future()
        self.pending[ident] = future
        try:
            async with asyncio.timeout(5):
                await self.socket.send(json.dumps({'id': ident, 'method': method, 'params': params or {}}))
                result = await future
            if self.failure:
                raise self.failure
            return result
        finally:
            self.pending.pop(ident, None)

    async def evaluate(self, expression: str) -> Any:
        result = await self.command('Runtime.evaluate', {'expression': expression, 'returnByValue': True})
        if result.get('exceptionDetails'):
            raise DeviceError('browser pool-form evaluation failed')
        return result.get('result', {}).get('value')

    async def _respond(self, method: str, params: dict) -> None:
        if len(self.acknowledgements) >= 32:
            raise DeviceError('too many outstanding browser request acknowledgements')
        self.sequence += 1
        self.acknowledgements.add(self.sequence)
        await self.socket.send(json.dumps({'id': self.sequence, 'method': method, 'params': params}))

    async def _request(self, event: dict) -> None:
        self.request_count += 1
        request, request_id = event['request'], event['requestId']
        method = request['method']
        params: dict[str, Any] = {'requestId': request_id}
        try:
            if self.request_count > 1024:
                raise DeviceError('browser request limit exceeded')
            if method not in ('GET', 'HEAD'):
                if method != 'PATCH' or request['url'] != self.device_url + '/api/system':
                    raise DeviceError('browser attempted an unexpected device write')
                raw = request.get('postData', '')
                if len(raw.encode()) > 32768 or self.saved_count >= 8:
                    raise DeviceError('browser pool-form write exceeds its bounds')
                payload = guarded_form_payload(json.loads(raw), self.pools)
                params['postData'] = base64.b64encode(json.dumps(payload).encode()).decode()
                # Let Chrome recompute Content-Length for the guarded body.
                params['headers'] = [{'name': key, 'value': value} for key, value in
                                     request.get('headers', {}).items() if key.lower() != 'content-length']
                self.saved_count += 1
        except Exception:
            await self._respond('Fetch.failRequest', {'requestId': request_id, 'errorReason': 'Aborted'})
            raise
        await self._respond('Fetch.continueRequest', params)

    async def _read(self) -> None:
        try:
            while True:
                message = json.loads(await self.socket.recv())
                ident = message.get('id')
                if message.get('method') == 'Fetch.requestPaused':
                    await self._request(message['params'])
                elif ident in self.acknowledgements:
                    self.acknowledgements.remove(ident)
                    if message.get('error'):
                        raise DeviceError('browser could not enforce the request guard')
                elif ident in self.pending:
                    future = self.pending[ident]
                    if not future.done():
                        if message.get('error'):
                            future.set_exception(DeviceError('browser command failed'))
                        else:
                            future.set_result(message.get('result', {}))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.failure = DeviceError('browser pool-form request guard or connection failed')
            self.failure.__cause__ = exc
            for future in self.pending.values():
                if not future.done():
                    future.set_exception(self.failure)

    async def open_form(self, *, reload: bool = False) -> None:
        token = f'form-reload-{self.sequence}'
        if reload:
            await self.evaluate('window.__fallbackReload=' + json.dumps(token))
            await self.command('Page.reload', {'ignoreCache': True})
        else:
            await self.command('Page.navigate', {'url': self.device_url + '/#/pool'})
        async with asyncio.timeout(15):
            while True:
                try:
                    ready = await self.evaluate("!!document.querySelector('#primaryPoolSelect span')" +
                        (' && window.__fallbackReload !== ' + json.dumps(token) if reload else ''))
                    if ready:
                        return
                except DeviceError:
                    if self.failure:
                        raise
                await asyncio.sleep(.1)

    async def select_role(self, role: str, index: int) -> None:
        if role not in ('primary', 'secondary') or index not in self.pools.owned:
            raise DeviceError('invalid browser role selection')
        selector = f'#{role}PoolSelect'
        await self.evaluate(f"document.querySelector({json.dumps(selector)}).querySelector('[tabindex]').click()")
        await asyncio.sleep(.1)
        ok = await self.evaluate("(() => {const e=[...document.querySelectorAll("
            + json.dumps(selector + ' li') + ")].find(e=>e.textContent.trim().startsWith("
            + json.dumps(f'Pool {index + 1}:') + "));if(!e)return false;e.click();return true;})()")
        if not ok:
            raise DeviceError('browser pool role option was not found')

    async def edit_worker(self, index: int, value: str) -> None:
        if index not in self.pools.owned:
            raise DeviceError('browser cannot edit an original pool')
        ok = await self.evaluate("(() => {const e=document.getElementById("
            + json.dumps(f'stratumUser_{index}') + ");if(!e)return false;"
            "const body=e.closest('[hidden]');if(body?.hidden)body.parentElement.firstElementChild.click();"
            "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(e,"
            + json.dumps(value) + ");e.dispatchEvent(new Event('input',{bubbles:true}));"
            "e.dispatchEvent(new Event('change',{bubbles:true}));return true;})()")
        if not ok:
            raise DeviceError('browser worker input was not found')

    async def values(self) -> dict:
        return await self.evaluate("(() => {const role=id=>{const s=document.querySelector(id+' span')?.textContent;"
            "const m=s?.match(/Pool (\\d+):/);return m?Number(m[1])-1:null;};"
            "const ids=" + json.dumps(sorted(self.pools.owned)) + ";return {primary:role('#primaryPoolSelect'),"
            "secondary:role('#secondaryPoolSelect'),workers:Object.fromEntries(ids.map(id=>[id,"
            "document.getElementById('stratumUser_'+id)?.value]))};})()")

    async def save(self) -> None:
        before = self.saved_count
        button = "[...document.querySelectorAll('app-pool button')].find(e=>e.textContent.trim()==='Save')"
        ok = await self.evaluate(f"(() => {{const e={button};if(!e||e.disabled)return false;e.click();return true;}})()")
        if not ok:
            raise DeviceError('browser Save button is disabled or missing')
        async with asyncio.timeout(15):
            while True:
                disabled = await self.evaluate(f'({button})?.disabled === true')
                if self.saved_count > before and disabled:
                    return
                await asyncio.sleep(.1)

    async def close(self) -> None:
        try:
            if self.socket is not None and self.reader is not None and not self.reader.done():
                await self.command('Fetch.disable')
        finally:
            if self.reader is not None:
                self.reader.cancel()
                await asyncio.gather(self.reader, return_exceptions=True)
                self.reader = None
            await super().close()
