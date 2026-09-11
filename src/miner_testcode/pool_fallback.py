"""ESP-Miner pool-transition fixtures; original pool rows are never rewritten."""
from __future__ import annotations

import asyncio
import copy
import json
import math
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

from .errors import ConfigError, DeviceError
from .interfaces.api import HttpApiInterface
from .interfaces.fake_stratum import FakeStratumV1Server, MiningJob

SELECTION = ("primaryPoolIndex", "secondaryPoolIndex", "useFallbackStratum")
OPERATING = ("miningPaused", "frequency", "coreVoltage", "autofanspeed",
             "manualFanSpeed", "minFanSpeed", "temptarget")


def bounded_number(settings: Mapping[str, Any], name: str, default: float,
                   low: float, high: float) -> float:
    value = settings.get(name, default)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ConfigError(f"pool_fallback_regression.{name} must be numeric")
    if not math.isfinite(value) or not low <= value <= high:
        raise ConfigError(f"pool_fallback_regression.{name} must be in {low}..{high}")
    return float(value)


def pool_table(info: Mapping[str, Any]) -> dict[int, dict[str, Any]]:
    rows = info.get("pools")
    if not isinstance(rows, list) or not 2 <= len(rows) <= 8:
        raise ConfigError("fallback regression requires the indexed pools API")
    result: dict[int, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, Mapping):
            raise ConfigError("invalid pool table")
        index = row.get("id")
        if type(index) is not int or not 0 <= index < 8 or index in result:
            raise ConfigError("pool IDs must be distinct integers in 0..7")
        result[index] = copy.deepcopy(dict(row))
    for key in SELECTION[:2]:
        if type(info.get(key)) is not int or info[key] not in result:
            raise ConfigError("selected pool is absent from the baseline")
    if info[SELECTION[0]] == info[SELECTION[1]]:
        raise ConfigError("primary and fallback must be distinct")
    if type(info.get("useFallbackStratum")) not in (int, bool) or info["useFallbackStratum"] not in (0, 1):
        raise ConfigError("invalid pool preference")
    return result


class TemporaryPools:
    def __init__(self, api: HttpApiInterface,
                 read_info: Callable[[], Awaitable[Mapping[str, Any]]],
                 baseline: Mapping[str, Any], *, read_only: bool) -> None:
        if read_only or api.read_only:
            raise ConfigError("pool fallback regression requires read_only=false")
        self.api, self.read_info = api, read_info
        self.original = pool_table(baseline)
        free = [i for i in range(8) if i not in self.original]
        if len(free) < 3:
            raise ConfigError("pool fallback regression needs three unused pool slots")
        self.ids = tuple(free[:3])
        self.baseline = {key: copy.deepcopy(baseline[key])
                         for key in (*SELECTION, *OPERATING) if key in baseline}
        if "miningPaused" not in self.baseline:
            raise ConfigError("baseline must report miningPaused")
        if baseline["miningPaused"]:
            raise ConfigError("pool fallback regression requires an unpaused device")
        self.entries: dict[int, dict[str, Any]] = {}
        self.owned: set[int] = set()
        self.started = False
        self.primary, self.secondary = self.ids[:2]

    async def install(self, host: str, primary_port: int, fallback_port: int,
                      difficulty: int, *, protocol: str = "SV1",
                      channel_type: str | None = None,
                      authority_keys: tuple[str, str] | None = None) -> None:
        # Validate all values before ownership or any write. Existing rows are
        # never copied into outgoing data, including masked password fields.
        if not isinstance(host, str) or not host.strip() or any(x in host for x in ("*", "<", ">", "${", "/", " ")):
            raise ConfigError("advertised_host must be a real miner-reachable host")
        for port in (primary_port, fallback_port):
            if type(port) is not int or not 1 <= port <= 65535:
                raise ConfigError("invalid temporary pool port")
        if type(difficulty) is not int or not 1 <= difficulty <= 65536:
            raise ConfigError("invalid temporary pool difficulty")
        if protocol not in ("SV1", "SV2"):
            raise ConfigError("temporary pool protocol must be SV1 or SV2")
        if protocol == "SV1" and (channel_type is not None or authority_keys is not None):
            raise ConfigError("SV2 settings require protocol SV2")
        if protocol == "SV2":
            alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
            if (channel_type not in ("standard", "extended") or
                    not isinstance(authority_keys, tuple) or len(authority_keys) != 2 or
                    any(not isinstance(key, str) or not 50 <= len(key) <= 60 or
                        any(c not in alphabet for c in key) for key in authority_keys)):
                raise ConfigError("SV2 requires a channel type and two disposable authority keys")
        for position, (index, label, port) in enumerate(zip(
                self.ids, ("primary", "fallback", "idle"),
                (primary_port, fallback_port, fallback_port))):
            self.entries[index] = {
                "id": index, "stratumProtocol": protocol, "stratumURL": host,
                "stratumPort": port, "stratumUser": f"fallback-regression.{label}",
                "stratumSuggestedDifficulty": difficulty, "stratumTLS": 0,
                "stratumCert": "", "stratumExtranonceSubscribe": False,
                "stratumDecodeCoinbase": True,
            }
            if protocol == "SV2":
                assert authority_keys is not None
                self.entries[index].update(
                    stratumV2ChannelType=channel_type,
                    stratumV2AuthorityPubkey=authority_keys[min(position, 1)],
                    stratumV2RequireAuth=True,
                )
        current = await self.read_info()
        if pool_table(current) != self.original or any(
            current.get(key) != value for key, value in self.baseline.items()
        ):
            raise DeviceError("device settings changed before temporary pool setup")
        self.started = True
        self.owned.update(self.ids)  # A failed response may still have created rows.
        await self.api.patch_json("/api/system", {"pools": list(self.entries.values())})
        await self.select(self.primary, self.secondary, 0)

    async def select(self, primary: int, secondary: int, preference: int | None = None,
                     *, save_entries: bool = False) -> None:
        if primary not in self.owned or secondary not in self.owned or primary == secondary:
            raise ConfigError("selection must use distinct owned temporary pools")
        payload: dict[str, Any] = {"primaryPoolIndex": primary, "secondaryPoolIndex": secondary}
        if preference is not None:
            if type(preference) is not int or preference not in (0, 1):
                raise ConfigError("pool preference must be 0 or 1")
            payload["useFallbackStratum"] = preference
        if save_entries:
            for index, entry in self.entries.items():
                if index not in self.owned or entry.get("id") != index or "stratumPassword" in entry:
                    raise ConfigError("settings save must contain only owned disposable pool rows")
                for field in ("stratumURL", "stratumUser"):
                    value = entry.get(field)
                    if not isinstance(value, str) or not value or any(x in value for x in ("<redacted", "*****", "${")):
                        raise ConfigError("refusing invalid or redacted temporary pool values")
            payload["pools"] = list(self.entries.values())
        await self.api.patch_json("/api/system", payload)
        self.primary, self.secondary = primary, secondary
        info = await self.read_info()
        if any(info.get(key) != value for key, value in payload.items() if key != "pools"):
            raise DeviceError("pool selection did not persist")
        if save_entries:
            table = pool_table(info)
            for index, entry in self.entries.items():
                if index not in table or any(table[index].get(k) != v for k, v in entry.items()):
                    raise DeviceError("temporary pool edit did not persist")

    async def restore(self) -> None:
        if not self.started:
            return
        info = await self.read_info()
        original_selection = {key: self.baseline[key] for key in SELECTION}
        if any(info.get(k) != v for k, v in original_selection.items()):
            await self.api.patch_json("/api/system", original_selection)
        info = await self.read_info()
        if any(info.get(k) != v for k, v in original_selection.items()):
            raise DeviceError("original selection not restored; refusing pool deletion")
        errors: list[Exception] = []
        existing = pool_table(info)
        for index in sorted(self.owned.intersection(existing)):
            try:
                await self.api.request("DELETE", f"/api/system/pools/{index}")
            except Exception as exc:
                errors.append(exc)
        final = await self.read_info()
        if pool_table(final) != self.original or any(
            final.get(key) != value for key, value in self.baseline.items()
        ):
            errors.append(DeviceError("original pool table or operating settings were not restored"))
        if errors:
            raise ExceptionGroup("temporary pool cleanup failed", errors)
        self.started = False


class WorkingPool(FakeStratumV1Server):
    """Automatically supply fresh jobs, including to primary recovery probes."""
    def __init__(self, label: str, host: str, difficulty: int, *, port: int = 0) -> None:
        super().__init__(host=host, port=port, client_line_limit=16384)
        self.label, self.difficulty = label, difficulty
        self.available = False
        self.job_counter = 0
        self.jobs: dict[str, int] = {}
        self.refresh: asyncio.Task[None] | None = None
        self.limit_error: str | None = None
        self.silent = False
        self.silent_requests = 0

    @property
    def mining_submissions(self):
        return self.submissions

    def _client_connected(self, reader, writer) -> None:
        if self._next_connection_id + len(self._client_tasks) > 64:
            self.limit_error = "fallback fake-pool connection limit exceeded"
            writer.close()
            return
        super()._client_connected(reader, writer)

    def _take_sequence(self) -> int:
        if self._next_sequence > 20000:
            self.limit_error = "fallback fake-pool request limit exceeded"
            raise ConnectionError(self.limit_error)
        return super()._take_sequence()

    async def start(self) -> None:
        await super().start()
        self.requested_port = self.port  # Reopening an endpoint preserves its port.
        self.available = True
        if self.refresh is None:
            self.refresh = asyncio.create_task(self._refresh(), name=f"fallback-work-{self.label}")

    async def set_available(self, available: bool) -> None:
        self.available = available
        if available:
            await self.start()
        else:
            await super().close()

    async def _handle_request(self, session, request) -> None:
        if self.silent:
            self.silent_requests += 1
            return  # Keep TCP open but withhold all protocol responses and jobs.
        await super()._handle_request(session, request)
        if request.method == "mining.authorize":
            await self._send_work(session)

    async def _send_work(self, session) -> None:
        if self.job_counter >= 4096:
            self.limit_error = "fallback fake-pool job limit exceeded"
            raise ConnectionError(self.limit_error)
        self.job_counter += 1
        job = MiningJob.standard(f"pf-{self.label}-{self.job_counter:x}")
        await self.send_job(job, difficulty=self.difficulty, session=session)
        self.jobs[job.job_id] = self.job_counter

    async def publish_work(self) -> None:
        if not self.available or self.silent:
            return
        authorized = {r.connection_id for r in self.requests if r.method == "mining.authorize"}
        for session in self.sessions:
            if session.connected and session.connection_id in authorized:
                try:
                    await self._send_work(session)
                except (ConnectionError, BrokenPipeError):
                    pass  # A recovery probe normally disconnects after one job.

    async def _refresh(self) -> None:
        while True:
            await asyncio.sleep(2)
            self.check_limits()
            await self.publish_work()

    def check_limits(self) -> None:
        if self.limit_error:
            raise DeviceError(self.limit_error)
        if self.refresh is not None and self.refresh.done():
            self.refresh.result()

    async def close(self) -> None:
        self.available = False
        if self.refresh is not None:
            self.refresh.cancel()
            await asyncio.gather(self.refresh, return_exceptions=True)
            self.refresh = None
        await super().close()


async def verify_restored_mining(
    pools: TemporaryPools, restart: Callable[[], Awaitable[Any]], *,
    timeout: float = 90, restart_after: float = 30, poll_interval: float = 1,
) -> bool:
    """Recover a latched pool-unavailable shutdown once, and report the restart.

    A connection receiving work with zero hashrate can remain powered down on
    affected firmware after all pools were unavailable. Never hide that recovery
    from the caller, and never restart a device reporting a safety fault.
    """
    started = time.monotonic()
    restarted = False
    accepted_baseline: int | None = None
    async with asyncio.timeout(timeout):
        while True:
            info = await pools.read_info()
            if pool_table(info) != pools.original or any(
                info.get(k) != v for k, v in pools.baseline.items()
            ):
                raise DeviceError("settings changed during post-cleanup mining verification")
            if info.get("hardware_fault") or info.get("power_fault") or info.get("overheat_mode"):
                raise DeviceError("device reports a safety fault after pool restoration")
            shares = int(info.get("sharesAccepted", 0))
            if accepted_baseline is None or shares < accepted_baseline:
                accepted_baseline = shares
            hashrate = float(info.get("hashRate", 0))
            work = int(info.get("workReceived", 0))
            if hashrate > 0 and work > 0 and shares > accepted_baseline:
                return restarted
            if (not restarted and hashrate == 0 and work > 0 and
                    time.monotonic() - started >= restart_after):
                restarted = True
                await restart()
                accepted_baseline = None
            await asyncio.sleep(poll_interval)


class PoolDashboard:
    """Optional bounded CDP connection to the configured miner's dashboard."""
    def __init__(self, endpoint: str, device_url: str) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"} or parsed.username or parsed.password:
            raise ConfigError("dashboard_cdp_url must be a loopback HTTP endpoint")
        self.endpoint = endpoint.rstrip("/")
        self.device_url = device_url.rstrip("/")
        self.socket = None
        self.sequence = 0

    async def start(self) -> None:
        api = HttpApiInterface(self.endpoint, read_only=True, retries=0)
        raw = await api.request("GET", "/json/list", max_bytes=65536)
        tabs = json.loads(raw)
        if not isinstance(tabs, list):
            raise DeviceError("invalid dashboard browser tab list")
        # AxeOS redirects its root dashboard to /#/. The fragment is client-side
        # routing, so it must not prevent matching this device's root page.
        device_page = urlsplit(self.device_url)._replace(fragment="").geturl().rstrip("/")
        target = next((t for t in tabs if isinstance(t, dict) and t.get("type") == "page" and
                       urlsplit(t.get("url", ""))._replace(fragment="").geturl().rstrip("/") == device_page), None)
        if target is None:
            raise DeviceError("open the configured miner dashboard in the CDP browser")
        ws_url = target.get("webSocketDebuggerUrl", "")
        if urlsplit(ws_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise DeviceError("dashboard debugger must remain on loopback")
        from websockets.asyncio.client import connect
        self.socket = await connect(ws_url, open_timeout=5, close_timeout=2, max_size=65536)
        await self._connected()
        await self.label()  # Verify the page before device writes.

    async def _connected(self) -> None:
        pass

    async def evaluate(self, expression: str) -> Any:
        if self.socket is None:
            raise DeviceError("dashboard browser is not connected")
        self.sequence += 1
        async with asyncio.timeout(5):
            await self.socket.send(json.dumps({"id": self.sequence, "method": "Runtime.evaluate",
                                              "params": {"expression": expression, "returnByValue": True}}))
            for _ in range(128):
                message = json.loads(await self.socket.recv())
                if message.get("id") == self.sequence:
                    result = message.get("result", {})
                    if message.get("error") or result.get("exceptionDetails"):
                        raise DeviceError("dashboard evaluation failed")
                    return result.get("result", {}).get("value")
            raise DeviceError("too many unrelated dashboard browser messages")

    async def label(self) -> str:
        value = await self.evaluate("document.querySelector('[gs-id=\"pool\"] app-dropdown span')?.textContent.trim()")
        if value not in {"Primary", "Fallback"}:
            raise DeviceError("dashboard pool dropdown is missing or unsupported")
        return value

    async def select(self, fallback: bool) -> None:
        await self.evaluate("document.querySelector('[gs-id=\"pool\"] app-dropdown [tabindex]').click()")
        await asyncio.sleep(0.1)
        label = "Fallback" if fallback else "Primary"
        selected = await self.evaluate("(() => {const e=[...document.querySelectorAll('[gs-id=\"pool\"] app-dropdown li')].find(e=>e.textContent.trim()==="
                                       + json.dumps(label) + ");if(!e)return false;e.click();return true;})()")
        if not selected:
            raise DeviceError("dashboard pool option was not found")

    async def close(self) -> None:
        if self.socket is not None:
            await self.socket.close()
            self.socket = None


async def wait_for_mining(
    read_info: Callable[[], Awaitable[Mapping[str, Any]]], pool: WorkingPool,
    pools: TemporaryPools, *, preference: int, fallback: int, timeout: float,
    poll_interval: float, observe: Callable[[dict[str, Any]], None],
    dashboard: PoolDashboard | None = None,
    stable_seconds: float = 0,
) -> Mapping[str, Any]:
    """Require fresh routed work and device acceptance, not a successful probe."""
    after_sequence = pool.requests[-1].sequence if pool.requests else 0
    after_job = pool.job_counter
    accepted_baseline: int | None = None
    previous_uptime: float | None = None
    started = time.monotonic()
    steady: tuple[float, int, int] | None = None
    expected_index = pools.secondary if fallback else pools.primary
    expected_user = pools.entries[expected_index]["stratumUser"]
    await pool.publish_work()
    async with asyncio.timeout(timeout):
        while True:
            pool.check_limits()
            info = await read_info()
            uptime = info.get("uptimeSeconds")
            if isinstance(uptime, (int, float)):
                if previous_uptime is not None and uptime < previous_uptime:
                    raise DeviceError("device restarted during pool transition")
                previous_uptime = uptime
            if info.get("hardware_fault") or info.get("power_fault") or info.get("overheat_mode") or info.get("miningPaused"):
                raise DeviceError("device fault or mining pause during fallback validation")
            label = await dashboard.label() if dashboard else None
            matches = (info.get("primaryPoolIndex") == pools.primary and
                       info.get("secondaryPoolIndex") == pools.secondary and
                       info.get("useFallbackStratum") == preference and
                       info.get("isUsingFallbackStratum") == fallback and
                       (dashboard is None or label == ("Fallback" if fallback else "Primary")))
            shares = int(info.get("sharesAccepted", 0))
            if not matches:
                accepted_baseline = None
            elif accepted_baseline is None or shares < accepted_baseline:
                accepted_baseline = shares
            connected = {s.connection_id for s in pool.sessions if s.connected}
            fresh = any(s.sequence > after_sequence and pool.jobs.get(s.job_id, 0) > after_job
                        and s.username == expected_user and s.connection_id in connected
                        for s in pool.mining_submissions)
            candidate = bool(matches and fresh and accepted_baseline is not None and
                             shares > accepted_baseline and int(info.get("workReceived", 0)) > 0)
            if not candidate:
                steady = None
            elif steady is None:
                steady = (time.monotonic(), shares, pool.job_counter)
            elif shares < steady[1]:
                steady = None
            steady_elapsed = time.monotonic() - steady[0] if steady else 0
            later_work = steady is not None and any(
                pool.jobs.get(s.job_id, 0) > steady[2] and s.username == expected_user
                and s.connection_id in connected for s in pool.mining_submissions
            )
            passed = candidate and (stable_seconds == 0 or bool(
                steady and steady_elapsed >= stable_seconds and
                shares > steady[1] and later_work
            ))
            observe({"elapsed_seconds": round(time.monotonic() - started, 3),
                     "preferred_fallback": info.get("useFallbackStratum"),
                     "active_fallback": info.get("isUsingFallbackStratum"),
                     "primary_index": info.get("primaryPoolIndex"),
                     "secondary_index": info.get("secondaryPoolIndex"),
                     "shares_accepted": shares, "work_received": info.get("workReceived"),
                     "fresh_submission": fresh, "dashboard_label": label,
                     "steady_seconds": round(steady_elapsed, 3), "passed": passed})
            if passed:
                return info
            await asyncio.sleep(poll_interval)
