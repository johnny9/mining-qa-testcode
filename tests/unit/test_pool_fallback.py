from __future__ import annotations

import asyncio
import copy
import json
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from miner_testcode.errors import ConfigError, DeviceError
from miner_testcode.pool_fallback import (
    PoolDashboard, TemporaryPools, WorkingPool, bounded_number, pool_table,
    wait_for_mining, verify_restored_mining,
)


def baseline():
    return {
        "pools": [{"id": 0, "stratumUser": "private-user-canary", "stratumPassword": "*****"},
                  {"id": 1, "stratumUser": "private-backup-canary", "stratumPassword": "*****"}],
        "primaryPoolIndex": 0, "secondaryPoolIndex": 1, "useFallbackStratum": 0,
        "miningPaused": False, "frequency": 600, "coreVoltage": 1150,
    }


class FakeApi:
    read_only = False

    def __init__(self):
        self.info = baseline()
        self.writes = []
        self.fail_after_patch = None
        self.ignore_restore = False
        self.fail_delete = None

    async def read(self):
        return copy.deepcopy(self.info)

    async def patch_json(self, path, payload):
        self.writes.append(("PATCH", path, copy.deepcopy(payload)))
        if self.ignore_restore and payload.get("primaryPoolIndex") == 0:
            return b""
        table = {r["id"]: r for r in self.info["pools"]}
        for row in payload.get("pools", []):
            table[row["id"]] = copy.deepcopy(row)
        self.info["pools"] = list(table.values())
        self.info.update({k: v for k, v in payload.items() if k != "pools"})
        if self.fail_after_patch == len(self.writes):
            raise OSError("response lost after write")
        return b""

    async def request(self, method, path):
        self.writes.append((method, path, None))
        index = int(path.rsplit("/", 1)[1])
        if index in (self.info["primaryPoolIndex"], self.info["secondaryPoolIndex"]):
            raise AssertionError("attempted deletion of a selected pool")
        if index == self.fail_delete:
            raise OSError("delete failed")
        self.info["pools"] = [r for r in self.info["pools"] if r["id"] != index]
        return b""


class TemporaryPoolTest(unittest.IsolatedAsyncioTestCase):
    def make(self, api=None, **kwargs):
        api = api or FakeApi()
        return api, TemporaryPools(api, api.read, api.info, read_only=kwargs.get("read_only", False))

    async def test_install_edit_swap_and_restore_without_original_writes(self):
        api, pools = self.make()
        original = copy.deepcopy(api.info)
        await pools.install("test-host", 3333, 3334, 256)
        primary, secondary, idle = pools.ids
        pools.entries[secondary]["stratumUser"] += "-edited"
        await pools.select(secondary, primary, save_entries=True)
        self.assertEqual(api.info["primaryPoolIndex"], secondary)
        self.assertNotIn("useFallbackStratum", api.writes[-1][2])
        await pools.restore()
        self.assertEqual(api.info, original)
        serialized = json.dumps(api.writes)
        for forbidden in ("private-user-canary", "private-backup-canary", "*****", "stratumPassword"):
            self.assertNotIn(forbidden, serialized)
        self.assertEqual([w[1] for w in api.writes if w[0] == "DELETE"],
                         [f"/api/system/pools/{i}" for i in (primary, secondary, idle)])

    async def test_read_only_rejected_before_write(self):
        for transport_read_only in (False, True):
            api = FakeApi()
            api.read_only = transport_read_only
            with self.assertRaises(ConfigError):
                TemporaryPools(api, api.read, api.info, read_only=not transport_read_only)
            self.assertEqual(api.writes, [])

    async def test_invalid_table_or_pause_rejected_before_write(self):
        for change in ({"pools": None}, {"primaryPoolIndex": 7}, {"secondaryPoolIndex": 0},
                       {"miningPaused": True}, {"useFallbackStratum": 2},
                       {"pools": [{"id": 0}, {"id": 0}]},
                       {"pools": [{"id": i} for i in range(6)]}):
            with self.subTest(change=change):
                api = FakeApi()
                api.info.update(change)
                with self.assertRaises(ConfigError):
                    TemporaryPools(api, api.read, api.info, read_only=False)
                self.assertEqual(api.writes, [])

    async def test_redacted_or_placeholder_endpoint_rejected_before_write(self):
        for host in ("<redacted>", "*****", "${HOST}", "http://pool", ""):
            api, pools = self.make()
            with self.assertRaises(ConfigError):
                await pools.install(host, 3333, 3334, 256)
            await pools.restore()
            self.assertEqual(api.writes, [])

    async def test_drift_before_install_rejected_before_write(self):
        api, pools = self.make()
        api.info["frequency"] = 700
        with self.assertRaises(DeviceError):
            await pools.install("test-host", 3333, 3334, 256)
        self.assertEqual(api.writes, [])

    async def test_partial_creation_and_partial_selection_are_cleaned(self):
        for failing_write in (1, 2):
            with self.subTest(failing_write=failing_write):
                api, pools = self.make()
                original = copy.deepcopy(api.info)
                api.fail_after_patch = failing_write
                with self.assertRaises(OSError):
                    await pools.install("test-host", 3333, 3334, 256)
                await pools.restore()
                self.assertEqual(api.info, original)

    async def test_cleanup_will_not_delete_until_original_selection_verified(self):
        api, pools = self.make()
        await pools.install("test-host", 3333, 3334, 256)
        api.ignore_restore = True
        with self.assertRaisesRegex(DeviceError, "refusing pool deletion"):
            await pools.restore()
        self.assertFalse(any(w[0] == "DELETE" for w in api.writes))

    async def test_delete_failure_is_visible_and_other_owned_rows_are_attempted(self):
        api, pools = self.make()
        await pools.install("test-host", 3333, 3334, 256)
        api.fail_delete = pools.ids[0]
        with self.assertRaises(ExceptionGroup):
            await pools.restore()
        self.assertEqual({r["id"] for r in api.info["pools"]}, {0, 1, pools.ids[0]})

    async def test_unrelated_operating_drift_is_reported(self):
        api, pools = self.make()
        await pools.install("test-host", 3333, 3334, 256)
        api.info["frequency"] = 700
        with self.assertRaises(ExceptionGroup):
            await pools.restore()

    async def test_unowned_selection_rejected(self):
        api, pools = self.make()
        with self.assertRaises(ConfigError):
            await pools.select(0, 1)
        self.assertEqual(api.writes, [])

    async def test_masked_password_and_redacted_edits_cannot_be_written(self):
        for field, value in (("stratumPassword", "*****"), ("stratumUser", "<redacted>"),
                             ("stratumURL", "${UNRESOLVED}"), ("id", 0)):
            with self.subTest(field=field):
                api, pools = self.make()
                await pools.install("test-host", 3333, 3334, 256)
                before = len(api.writes)
                pools.entries[pools.primary][field] = value
                with self.assertRaises(ConfigError):
                    await pools.select(pools.primary, pools.secondary, save_entries=True)
                self.assertEqual(len(api.writes), before)
                await pools.restore()


class MiningEvidenceTest(unittest.IsolatedAsyncioTestCase):
    async def test_restored_mining_requires_progress_and_recovers_stalled_power_once(self):
        for stalled in (False, True):
            with self.subTest(stalled=stalled):
                api = FakeApi()
                api.info.update(hashRate=0 if stalled else 100, workReceived=3, sharesAccepted=0)
                pools = TemporaryPools(api, api.read, api.info, read_only=False)
                async def read():
                    if api.info["hashRate"]:
                        api.info["sharesAccepted"] += 1
                    return await api.read()
                pools.read_info = read
                async def restart():
                    api.info["hashRate"] = 100
                callback = AsyncMock(side_effect=restart)
                restarted = await verify_restored_mining(pools, callback, timeout=.1,
                                                         restart_after=.005, poll_interval=.001)
                self.assertEqual(restarted, stalled)
                self.assertEqual(callback.await_count, int(stalled))

    async def test_post_cleanup_fault_or_missing_shares_never_pass(self):
        api = FakeApi()
        api.info.update(hashRate=100, workReceived=3, sharesAccepted=0)
        pools = TemporaryPools(api, api.read, api.info, read_only=False)
        callback = AsyncMock()
        with self.assertRaises(TimeoutError):
            await verify_restored_mining(pools, callback, timeout=.01, poll_interval=.001)
        callback.assert_not_awaited()
        api.info["overheat_mode"] = 1
        with self.assertRaises(DeviceError):
            await verify_restored_mining(pools, callback, timeout=.01, poll_interval=.001)
        callback.assert_not_awaited()

    async def test_initial_pool_timeout_is_setup_error(self):
        from tests.e2e.test_pool_fallback_regression import PoolFallbackRegressionTest
        case = PoolFallbackRegressionTest("test_manual_switch_failover_and_recovery")
        case.chart = lambda *a, **kw: None
        case.device = SimpleNamespace(current_info=AsyncMock())
        case.pools = None
        case.phase_timeout, case.poll_interval, case.dashboard = 5, 1, None
        with patch("tests.e2e.test_pool_fallback_regression.wait_for_mining", new=AsyncMock(side_effect=TimeoutError)):
            with self.assertRaisesRegex(DeviceError, "local-pool setup"):
                await case._phase("initial-primary", None, preference=0, fallback=0)

    async def test_silent_fault_is_released_before_failed_phase_cleanup(self):
        from tests.e2e.test_pool_fallback_regression import PoolFallbackRegressionTest
        case = PoolFallbackRegressionTest('test_silent_primary_fails_over_and_recovers')
        case.primary_pool = SimpleNamespace(silent=False, publish_work=AsyncMock(),
                                            sessions=[SimpleNamespace(connected=True)])
        case.fallback_pool = None
        case._phase = AsyncMock(side_effect=AssertionError('no failover'))
        with self.assertRaisesRegex(AssertionError, 'no failover'):
            await case.test_silent_primary_fails_over_and_recovers()
        self.assertFalse(case.primary_pool.silent)
        case.primary_pool.publish_work.assert_awaited_once()

    async def exercise(self, *, fresh=True, worker=True, flags=True, progress=True,
                       old_job=False, disconnected=False, reconnect=False, label="Fallback",
                       stable_seconds=0, ongoing=False, flap=False):
        api = FakeApi()
        pools = TemporaryPools(api, api.read, api.info, read_only=False)
        await pools.install("test-host", 3333, 3334, 256)
        info = {**api.info, "isUsingFallbackStratum": 1, "sharesAccepted": 10, "workReceived": 1}
        pool = SimpleNamespace(requests=[SimpleNamespace(sequence=10)], job_counter=10,
                               jobs={"old": 1}, submissions=[], sessions=[SimpleNamespace(connection_id=1, connected=not disconnected)])

        async def publish():
            pool.job_counter += 1
            pool.jobs["new"] = pool.job_counter
        pool.publish_work = publish
        pool.check_limits = lambda: None
        calls = 0

        async def read():
            nonlocal calls
            calls += 1
            result = dict(info)
            if progress:
                result["sharesAccepted"] += calls
            if not flags or (reconnect and calls == 1) or (flap and calls == 4):
                result["isUsingFallbackStratum"] = 0
            if fresh and (calls == 2 or ongoing and calls > 2):
                job = 'new'
                if ongoing:
                    pool.job_counter += 1
                    job = f'new-{calls}'
                    pool.jobs[job] = pool.job_counter
                pool.submissions.append(SimpleNamespace(sequence=10 + calls, job_id="old" if old_job else job,
                    username=pools.entries[pools.secondary]["stratumUser"] if worker else "wrong-worker",
                    connection_id=1))
            return result

        async def dashboard_label():
            return label
        observations = []
        # Advance phase time with observations, so a slow CI host cannot let
        # the stability assertion pass before the deliberately injected flap.
        with patch('miner_testcode.pool_fallback.time',
                   SimpleNamespace(monotonic=lambda: calls * .001)):
            result = await wait_for_mining(read, pool, pools, preference=0, fallback=1,
                                           timeout=0.1, poll_interval=0.001, observe=observations.append,
                                           dashboard=SimpleNamespace(label=dashboard_label),
                                           stable_seconds=stable_seconds)
        self.assertGreater(result["sharesAccepted"], 10)
        self.assertTrue(observations[-1]["passed"])
        self.assertNotIn("stratumUser", json.dumps(observations))
        return observations

    async def test_fresh_routed_submission_and_counter_progress_pass(self):
        await self.exercise()

    async def test_transient_reconnect_is_allowed(self):
        await self.exercise(reconnect=True)

    async def test_stability_requires_later_jobs_and_shares(self):
        observations = await self.exercise(stable_seconds=.005, ongoing=True)
        self.assertGreaterEqual(observations[-1]['steady_seconds'], .005)
        with self.assertRaises(TimeoutError):
            await self.exercise(stable_seconds=.005)

    async def test_wrong_pool_during_stability_restarts_the_window(self):
        observations = await self.exercise(stable_seconds=.005, ongoing=True, flap=True, label='Fallback')
        wrong = next(i for i, row in enumerate(observations) if row['active_fallback'] == 0)
        self.assertFalse(observations[wrong]['passed'])
        self.assertEqual(observations[wrong + 1]['steady_seconds'], 0)

    async def test_stale_probe_wrong_worker_counter_or_label_cannot_pass(self):
        for kwargs in ({"fresh": False}, {"worker": False}, {"flags": False},
                       {"progress": False}, {"old_job": True}, {"disconnected": True},
                       {"label": "Primary"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(TimeoutError):
                await self.exercise(**kwargs)


class WorkingPoolTest(unittest.IsolatedAsyncioTestCase):
    async def test_silent_pool_keeps_connection_open_and_withholds_protocol(self):
        pool = WorkingPool('primary', '127.0.0.1', 256)
        self.addAsyncCleanup(pool.close)
        await pool.start()
        reader, writer = await asyncio.open_connection('127.0.0.1', pool.port)
        try:
            writer.write(b'{"id":1,"method":"mining.authorize","params":["test-worker","x"]}\n')
            await writer.drain()
            for _ in range(3):
                await asyncio.wait_for(reader.readline(), 1)
            pool.silent = True
            writer.write(b'{"id":2,"method":"mining.subscribe","params":[]}\n')
            await writer.drain()
            await pool.publish_work()
            with self.assertRaises(TimeoutError):
                await asyncio.wait_for(reader.readline(), .02)
            self.assertGreater(pool.silent_requests, 0)
            self.assertTrue(pool.sessions[0].connected)
            pool.silent = False
            await pool.publish_work()
            messages = [json.loads(await asyncio.wait_for(reader.readline(), 1)) for _ in range(2)]
            self.assertTrue(any(m.get('method') == 'mining.notify' for m in messages))
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_resource_limits_fail_closed(self):
        pool = WorkingPool("primary", "127.0.0.1", 256)
        pool._next_sequence = 20001
        with self.assertRaises(ConnectionError):
            pool._take_sequence()
        with self.assertRaises(DeviceError):
            pool.check_limits()
        self.assertEqual(pool.requests, ())

        pool = WorkingPool("primary", "127.0.0.1", 256)
        pool.job_counter = 4096
        with self.assertRaises(ConnectionError):
            await pool._send_work(None)
        self.assertEqual(pool.jobs, {})

    async def test_dashboard_attaches_after_axeos_hash_route_redirect(self):
        dashboard = PoolDashboard("http://127.0.0.1:9224", "http://miner")
        tabs = [{"type": "page", "url": "http://miner/#/",
                 "webSocketDebuggerUrl": "ws://127.0.0.1:9224/devtools/page/test"}]
        socket = AsyncMock()
        socket.recv.return_value = json.dumps({"id": 1, "result": {"result": {"value": "Primary"}}})
        with patch("miner_testcode.pool_fallback.HttpApiInterface.request", new=AsyncMock(return_value=json.dumps(tabs).encode())), \
             patch("websockets.asyncio.client.connect", new=AsyncMock(return_value=socket)) as connect:
            await dashboard.start()
            connect.assert_awaited_once()
            await dashboard.close()
            socket.close.assert_awaited_once()

    async def test_authorize_sends_fresh_work_and_endpoint_can_reopen(self):
        pool = WorkingPool("primary", "127.0.0.1", 256)
        self.addAsyncCleanup(pool.close)
        await pool.start()
        port = pool.port
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        try:
            writer.write(json.dumps({"id": 1, "method": "mining.authorize", "params": ["test-worker", "secret-canary"]}).encode() + b"\n")
            await writer.drain()
            messages = [json.loads(await asyncio.wait_for(reader.readline(), 1)) for _ in range(3)]
            job = next(m for m in messages if m.get("method") == "mining.notify")
            self.assertIn(job["params"][0], pool.jobs)
            self.assertNotIn("secret-canary", repr(pool.requests))
            await pool.set_available(False)
            self.assertEqual(await asyncio.wait_for(reader.read(), 1), b"")
            await pool.set_available(True)
            self.assertEqual(pool.port, port)
        finally:
            writer.close()
            await writer.wait_closed()


class FallbackConfigurationTest(unittest.TestCase):
    def test_invalid_limits(self):
        for value in (True, "20", float("nan"), float("inf"), 0, 301):
            with self.subTest(value=value), self.assertRaises(ConfigError):
                bounded_number({"timeout": value}, "timeout", 180, 5, 300)

    def test_dashboard_requires_loopback(self):
        for endpoint in ("http://remote-host:9224", "https://localhost:9224", "http://user:secret@localhost:9224"):
            with self.assertRaises(ConfigError):
                PoolDashboard(endpoint, "http://miner")

    def test_disabled_suite_skips_before_hardware_and_validation_is_opt_in(self):
        from tests.e2e.test_pool_fallback_regression import PoolFallbackRegressionTest
        method = PoolFallbackRegressionTest.test_validation_settings_save_and_pool_role_swap
        self.assertEqual(method.validation_prs, frozenset({1957, 1962}))
        case = PoolFallbackRegressionTest("test_manual_switch_failover_and_recovery")
        case._context = SimpleNamespace(validation_prs=frozenset(), project=SimpleNamespace(test_settings=lambda _: {}))
        with self.assertRaises(unittest.SkipTest):
            case.setUp()


if __name__ == "__main__":
    unittest.main()
