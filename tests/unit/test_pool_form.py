from __future__ import annotations

import asyncio
import base64
import copy
import json
import unittest

from miner_testcode.errors import DeviceError
from miner_testcode.pool_fallback import TemporaryPools
from miner_testcode.pool_form import PoolSettingsForm, guarded_form_payload
from tests.unit.test_pool_fallback import FakeApi


class FormGuardTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.api = FakeApi()
        self.pools = TemporaryPools(self.api, self.api.read, self.api.info, read_only=False)
        await self.pools.install('test-host', 4333, 4334, 256)
        self.payload = {
            'primaryPoolIndex': self.pools.primary,
            'secondaryPoolIndex': self.pools.secondary,
            'pools': copy.deepcopy(self.api.info['pools']),
        }
        for row in self.payload['pools']:
            row['stratumPassword'] = '*****'

    async def test_guard_preserves_submitted_edits_and_removes_originals_and_passwords(self):
        p, s, _ = self.pools.ids
        self.payload['primaryPoolIndex'], self.payload['secondaryPoolIndex'] = s, p
        next(r for r in self.payload['pools'] if r['id'] == s)['stratumUser'] += '-ui'
        safe = guarded_form_payload(self.payload, self.pools)
        self.assertEqual((safe['primaryPoolIndex'], safe['secondaryPoolIndex']), (s, p))
        self.assertEqual({r['id'] for r in safe['pools']}, self.pools.owned)
        self.assertTrue(next(r for r in safe['pools'] if r['id'] == s)['stratumUser'].endswith('-ui'))
        for forbidden in ('*****', 'stratumPassword', 'private-user-canary', 'private-backup-canary'):
            self.assertNotIn(forbidden, json.dumps(safe))

    async def test_guard_rejects_original_edits_bad_roles_and_partial_rows(self):
        bad = []
        for key, value in (('primaryPoolIndex', 0), ('secondaryPoolIndex', self.pools.primary),
                           ('primaryPoolIndex', True), ('miningPaused', True)):
            payload = copy.deepcopy(self.payload)
            payload[key] = value
            bad.append(payload)
        payload = copy.deepcopy(self.payload)
        payload['pools'][0]['stratumUser'] = 'changed-original'
        bad.append(payload)
        for field, value in (('stratumURL', 'unexpected-host'), ('stratumPassword', 'new-secret'),
                             ('stratumUser', 'private-user'), ('id', 7)):
            payload = copy.deepcopy(self.payload)
            payload['pools'][2][field] = value
            bad.append(payload)
        payload = copy.deepcopy(self.payload)
        payload['pools'].pop()
        bad.append(payload)
        payload = copy.deepcopy(self.payload)
        payload['pools'].append(payload['pools'][-1])
        bad.append(payload)
        payload = copy.deepcopy(self.payload)
        del payload['pools'][2]['stratumURL']
        bad.append(payload)
        for payload in bad:
            with self.assertRaises(DeviceError):
                guarded_form_payload(payload, self.pools)

    async def test_cdp_handles_guard_events_while_evaluation_is_pending(self):
        form, socket = await self.connect()
        await socket.incoming.put(json.dumps({'method': 'Fetch.requestPaused', 'params': {
            'requestId': 'save-1', 'request': {'method': 'PATCH', 'url': 'http://miner/api/system',
                'postData': json.dumps(self.payload), 'headers': {'Content-Length': '9999'}},
        }}))
        self.assertEqual(await form.evaluate('read the form'), 'ready')
        await asyncio.sleep(0)
        continued = next(m for m in socket.sent if m['method'] == 'Fetch.continueRequest')
        safe = json.loads(base64.b64decode(continued['params']['postData']))
        self.assertEqual({r['id'] for r in safe['pools']}, self.pools.owned)
        self.assertEqual(continued['params']['headers'], [])
        self.assertEqual(form.saved_count, 1)
        self.assertNotIn('*****', json.dumps(safe))

    async def test_cdp_aborts_unexpected_device_write(self):
        form, socket = await self.connect()
        await socket.incoming.put(json.dumps({'method': 'Fetch.requestPaused', 'params': {
            'requestId': 'bad', 'request': {'method': 'POST', 'url': 'http://miner/api/system/restart'},
        }}))
        with self.assertRaises(DeviceError):
            await form.evaluate('wait for the rejected request')
        self.assertTrue(any(m['method'] == 'Fetch.failRequest' for m in socket.sent))
        self.assertFalse(any(m['method'] == 'Fetch.continueRequest' for m in socket.sent))
        self.assertEqual(form.saved_count, 0)

    async def test_cdp_aborts_malformed_json_and_request_limit(self):
        for limit in (False, True):
            form, socket = await self.connect()
            if limit:
                form.request_count = 1024
            await socket.incoming.put(json.dumps({'method': 'Fetch.requestPaused', 'params': {
                'requestId': 'bad', 'request': {'method': 'PATCH', 'url': 'http://miner/api/system',
                                              'postData': 'invalid json'},
            }}))
            with self.assertRaises(DeviceError):
                await form.evaluate('wait')
            self.assertTrue(any(m['method'] == 'Fetch.failRequest' for m in socket.sent))

    async def connect(self):
        form = PoolSettingsForm('http://127.0.0.1:9226', 'http://miner', self.pools)
        socket = FakeSocket()
        form.socket = socket
        await form._connected()
        self.addAsyncCleanup(form.close)
        return form, socket


class FakeSocket:
    def __init__(self):
        self.sent = []
        self.incoming = asyncio.Queue()

    async def send(self, raw):
        message = json.loads(raw)
        self.sent.append(message)
        result = {'result': {'value': 'ready'}} if message['method'] == 'Runtime.evaluate' else {}
        await self.incoming.put(json.dumps({'id': message['id'], 'result': result}))

    async def recv(self):
        return await self.incoming.get()

    async def close(self):
        pass
