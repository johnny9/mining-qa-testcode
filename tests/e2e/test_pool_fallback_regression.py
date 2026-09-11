from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from miner_testcode import capabilities as caps
from miner_testcode.artifacts import append_jsonl
from miner_testcode.errors import ConfigError, DeviceError
from miner_testcode.pool_fallback import (
    PoolDashboard, TemporaryPools, WorkingPool, bounded_number, wait_for_mining,
    verify_restored_mining,
)
from miner_testcode.testcase import MinerTestCase, validation_test
from miner_testcode.pool_form import PoolSettingsForm


class PoolFallbackRegressionTest(MinerTestCase):
    """Pool transition correctness, independent of probe/reconnect policy."""
    required_capabilities = frozenset({caps.API, caps.MINING_STATE, caps.POOL_CONFIG, caps.STRATUM_V1})

    def setUp(self) -> None:
        super().setUp()
        self.settings = self.settings_for("pool_fallback_regression")
        if self.settings.get("enabled", False) is not True:
            self.skipTest("enable tests.pool_fallback_regression.enabled explicitly")
        if self.device_config.options.get("read_only") is not False:
            raise ConfigError("pool fallback regression requires explicit read_only=false")
        self.host = str(self.settings.get("advertised_host", "")).strip()
        if not self.host or self.host in {"0.0.0.0", "::", "localhost", "::1"} or self.host.startswith("127."):
            raise ConfigError("advertised_host must be reachable from the miner")
        self.bind_host = str(self.settings.get("bind_host", "127.0.0.1"))
        self.phase_timeout = bounded_number(self.settings, "phase_timeout", 180, 5, 300)
        self.poll_interval = bounded_number(self.settings, "poll_interval", 1, 0.25, 5)
        self.stable_seconds = bounded_number(self.settings, "stable_seconds", 5, 0, 60)
        self.outage_seconds = bounded_number(self.settings, "outage_seconds", 45, 15, 180)
        cycles = bounded_number(self.settings, "transition_cycles", 3, 2, 5)
        if not cycles.is_integer() or self.stable_seconds >= self.phase_timeout:
            raise ConfigError("transition_cycles must be an integer and stable_seconds below phase_timeout")
        self.transition_cycles = int(cycles)
        if self._testMethodName == 'test_pool_settings_form' and not self.settings.get('dashboard_cdp_url'):
            self.skipTest('pool-settings form validation requires dashboard_cdp_url')
        difficulty = bounded_number(self.settings, "share_difficulty", 256, 1, 65536)
        if not difficulty.is_integer():
            raise ConfigError("share_difficulty must be an integer")
        self.difficulty = int(difficulty)
        self.ports = []
        for key in ("primary_port", "fallback_port"):
            port = bounded_number(self.settings, key, 0, 0, 65535)
            if not port.is_integer():
                raise ConfigError(f"{key} must be an integer")
            self.ports.append(int(port))
        if self.ports[0] and self.ports[0] == self.ports[1]:
            raise ConfigError("primary_port and fallback_port must be distinct")
        self.dashboard: PoolDashboard | None = None

    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        info = await self.device.current_info()
        for setting, field in (("expected_hostname", "hostname"), ("expected_version", "version")):
            expected = self.settings.get(setting)
            if expected is not None and info.get(field) != expected:
                self.fail(f"device {field} does not match the requested test target")
        if float(info.get("hashRate", 0)) <= 0:
            raise DeviceError("pool fallback regression requires initially healthy mining")
        if not hasattr(self.device, "api"):
            self.skipTest("requires an adapter exposing the indexed ESP-Miner API")
        self.pools = TemporaryPools(self.device.api, self.device.current_info, info,
                                    read_only=self.device.read_only)
        self.primary_pool = WorkingPool("primary", self.bind_host, self.difficulty, port=self.ports[0])
        self.fallback_pool = WorkingPool("fallback", self.bind_host, self.difficulty, port=self.ports[1])
        for pool in (self.primary_pool, self.fallback_pool):
            self.addCleanup(pool.write_transcript, self.artifacts.path / f"{pool.label}-stratum.jsonl")
            self.addAsyncCleanup(pool.close)
            await pool.start()
        endpoint = self.settings.get("dashboard_cdp_url")
        if endpoint:
            self.dashboard = PoolDashboard(str(endpoint), self.device.api.base_url)
            self.addAsyncCleanup(self.dashboard.close)
            await self.dashboard.start()
        self.addAsyncCleanup(self._restore_temporary_pools)
        self.chart("Installing temporary fallback regression pools")
        await self.pools.install(self.host, self.primary_pool.port,
                                 self.fallback_pool.port, self.difficulty)
        await self._phase("initial-primary", self.primary_pool, preference=0, fallback=0)

    async def _restore_temporary_pools(self) -> None:
        evidence = {"settings_restored": False, "mining_restored": False,
                    "recovery_restart_required": False}

        async def recover() -> None:
            evidence["recovery_restart_required"] = True
            self.logger.warning("Mining stayed powered down after pool restoration; recovering with one restart")
            await self.device._restart_and_wait(expected=self.pools.baseline)

        try:
            assert self._context is not None
            async with asyncio.timeout(self._context.project.runner.cleanup_timeout):
                await self.pools.restore()
                evidence["settings_restored"] = True
                if not self.pools.owned:
                    return
                await verify_restored_mining(self.pools, recover)
                evidence["mining_restored"] = True
        finally:
            append_jsonl(self.artifacts.path / "pool-cleanup.jsonl", evidence)
        self.chart("Original pool entries and operating settings restored", status="good")
        if evidence["recovery_restart_required"]:
            raise DeviceError("Original settings and mining restored, but firmware required a recovery restart")

    async def _phase(self, name: str, pool: WorkingPool, *, preference: int, fallback: int,
                     check_dashboard: bool = True) -> None:
        self.chart("Pool phase: %s", name)

        def observe(sample: dict[str, Any]) -> None:
            self.primary_pool.check_limits()
            self.fallback_pool.check_limits()
            append_jsonl(self.artifacts.path / "pool-phases.jsonl", {"phase": name, **sample})

        try:
            await wait_for_mining(self.device.current_info, pool, self.pools,
                                  preference=preference, fallback=fallback,
                                  timeout=self.phase_timeout, poll_interval=self.poll_interval,
                                  observe=observe, dashboard=self.dashboard if check_dashboard else None,
                                  stable_seconds=getattr(self, 'stable_seconds', 0))
        except TimeoutError:
            if name == "initial-primary":
                raise DeviceError(
                    "local-pool setup could not establish mining; check miner-to-host "
                    "reachability and the Stratum transcript before interpreting a regression"
                ) from None
            self.fail(f"{name}: no matching active pool and fresh accepted share within {self.phase_timeout:g}s")
        self.chart("Pool phase passed: %s", name, status="good")

    async def _manual_select(self, fallback: int) -> None:
        if self.dashboard:
            await self.dashboard.select(bool(fallback))
        else:
            await self.device.api.patch_json("/api/system", {"useFallbackStratum": fallback})

    async def test_manual_switch_failover_and_recovery(self) -> None:
        await self._manual_select(1)
        await self._phase("manual-fallback", self.fallback_pool, preference=1, fallback=1)
        await self._manual_select(0)
        await self._phase("manual-primary", self.primary_pool, preference=0, fallback=0)

        # Endpoint outage, not a preference write, forces automatic failover.
        await self.primary_pool.set_available(False)
        await self._phase("automatic-fallback", self.fallback_pool, preference=0, fallback=1)
        await self.primary_pool.set_available(True)
        await self._phase("automatic-recovery", self.primary_pool, preference=0, fallback=0)

    async def _verify_saved(self, primary: int, secondary: int) -> None:
        info = await self.device.current_info()
        self.assertEqual(info['primaryPoolIndex'], primary)
        self.assertEqual(info['secondaryPoolIndex'], secondary)
        table = {row['id']: row for row in info['pools']}
        for index, expected in self.pools.entries.items():
            self.assertTrue(all(table[index].get(k) == v for k, v in expected.items()),
                            'temporary pool edit did not persist')
        self.pools.primary, self.pools.secondary = primary, secondary

    async def test_active_edits_and_manually_preferred_fallback(self) -> None:
        primary, secondary, _ = self.pools.ids
        self.pools.entries[primary]['stratumUser'] += '-active-edit'
        await self.device.api.patch_json('/api/system', {'pools': [self.pools.entries[primary]]})
        await self._verify_saved(primary, secondary)
        await self._phase('active-primary-edited', self.primary_pool, preference=0, fallback=0)

        await self._manual_select(1)
        await self._phase('manually-preferred-fallback', self.fallback_pool, preference=1, fallback=1)
        self.pools.entries[secondary]['stratumUser'] += '-active-edit'
        await self.pools.select(primary, secondary, save_entries=True)
        await self._phase('preferred-fallback-saved', self.fallback_pool, preference=1, fallback=1)

        await self._manual_select(0)
        await self._phase('primary-before-correction', self.primary_pool, preference=0, fallback=0)
        await self.primary_pool.set_available(False)
        await self._phase('fallback-before-primary-correction', self.fallback_pool, preference=0, fallback=1)
        # Correct the preferred row to a reachable port without changing either
        # role index. A distinct worker proves that the edited row supplies work.
        self.pools.entries[primary]['stratumPort'] = self.fallback_pool.port
        self.pools.entries[primary]['stratumUser'] += '-corrected'
        await self.device.api.patch_json('/api/system', {'pools': [self.pools.entries[primary]]})
        await self._verify_saved(primary, secondary)
        await self._phase('corrected-primary-recovered', self.fallback_pool, preference=0, fallback=0)

    async def _both_pools_outage(self, *, restore_fallback: bool) -> None:
        await self.primary_pool.set_available(False)
        await self.fallback_pool.set_available(False)
        started = time.monotonic()
        previous_uptime = None
        settled = False
        async with asyncio.timeout(self.outage_seconds + 30):
            while time.monotonic() - started < self.outage_seconds:
                info = await self.device.current_info()
                if any(info.get(k) for k in ('hardware_fault', 'power_fault', 'overheat_mode', 'miningPaused')):
                    raise DeviceError('device fault or pause during the two-pool outage')
                uptime = info.get('uptimeSeconds', 0)
                if previous_uptime is not None and uptime < previous_uptime:
                    self.fail('device restarted during the two-pool outage')
                previous_uptime = uptime
                settled = settled or info.get('workReceived') == 0
                append_jsonl(self.artifacts.path / 'pool-outage.jsonl', {
                    'elapsed_seconds': round(time.monotonic() - started, 3),
                    'work_received': info.get('workReceived'), 'hashrate_ghs': info.get('hashRate'),
                    'shares_accepted': info.get('sharesAccepted'),
                })
                await asyncio.sleep(self.poll_interval)
        self.assertTrue(settled, 'miner did not observe loss of work during the outage')
        pool = self.fallback_pool if restore_fallback else self.primary_pool
        await pool.set_available(True)
        await self._phase('both-down-recover-' + pool.label, pool,
                          preference=0, fallback=int(restore_fallback))

    async def test_both_pools_down_then_primary_recovers(self) -> None:
        await self._both_pools_outage(restore_fallback=False)

    async def test_both_pools_down_then_fallback_recovers(self) -> None:
        await self._both_pools_outage(restore_fallback=True)

    async def test_repeated_failover_and_recovery(self) -> None:
        for cycle in range(1, self.transition_cycles + 1):
            await self.primary_pool.set_available(False)
            await self._phase(f'cycle-{cycle}-fallback', self.fallback_pool, preference=0, fallback=1)
            await self.primary_pool.set_available(True)
            await self._phase(f'cycle-{cycle}-recovery', self.primary_pool, preference=0, fallback=0)

    async def test_silent_primary_fails_over_and_recovers(self) -> None:
        self.assertTrue(any(s.connected for s in self.primary_pool.sessions))
        self.primary_pool.silent = True  # Existing TCP connections remain open.
        try:
            await self._phase('silent-primary-fallback', self.fallback_pool, preference=0, fallback=1)
            self.assertGreater(self.primary_pool.silent_requests, 0,
                               'silent endpoint did not receive miner requests')
        finally:
            # Release the injected stall before restoration, including when the
            # firmware never fails over and the phase assertion times out.
            self.primary_pool.silent = False
            await self.primary_pool.publish_work()
        await self._phase('silent-primary-recovery', self.primary_pool, preference=0, fallback=0)

    async def test_pool_settings_form(self) -> None:
        assert self.dashboard is not None
        form = PoolSettingsForm(str(self.settings['dashboard_cdp_url']),
                                self.device.api.base_url, self.pools)

        async def dashboard_page() -> None:
            await self.dashboard.evaluate('location.href=' + json.dumps(self.device.api.base_url + '/#/'))
            async with asyncio.timeout(15):
                while True:
                    try:
                        await self.dashboard.label()
                        return
                    except DeviceError:
                        await asyncio.sleep(.1)

        async def close_form() -> None:
            try:
                await form.close()
            finally:
                await dashboard_page()

        self.addAsyncCleanup(close_form)
        await form.start()
        await form.open_form()
        primary, secondary, idle = self.pools.ids

        async def check_form(p: int, s: int) -> None:
            values = await form.values()
            self.assertEqual((values['primary'], values['secondary']), (p, s))
            self.assertEqual(values['workers'], {
                str(i): row['stratumUser'] for i, row in self.pools.entries.items()
            })

        self.pools.entries[secondary]['stratumUser'] += '-ui-first'
        await form.edit_worker(secondary, self.pools.entries[secondary]['stratumUser'])
        # Secondary-first then primary collisions exercise previousPrim history
        # across two saves in the same component instance (the #1962 fix).
        await form.select_role('secondary', primary)
        await check_form(secondary, primary)
        await form.save()
        await self._verify_saved(secondary, primary)
        await self._phase('form-secondary-swap', self.fallback_pool, preference=0, fallback=0,
                          check_dashboard=False)

        self.pools.entries[primary]['stratumUser'] += '-ui-second'
        await form.edit_worker(primary, self.pools.entries[primary]['stratumUser'])
        await form.select_role('primary', primary)
        await check_form(primary, secondary)
        await form.save()
        await self._verify_saved(primary, secondary)
        await self._phase('form-primary-swap', self.primary_pool, preference=0, fallback=0,
                          check_dashboard=False)

        await form.open_form(reload=True)
        await check_form(primary, secondary)
        self.pools.entries[idle]['stratumUser'] += '-ui-after-reload'
        await form.edit_worker(idle, self.pools.entries[idle]['stratumUser'])
        await form.save()
        await self._verify_saved(primary, secondary)
        await form.open_form(reload=True)
        await check_form(primary, secondary)
        self.assertEqual(form.saved_count, 3)
        append_jsonl(self.artifacts.path / 'pool-form.jsonl', {
            'guarded_saves': form.saved_count, 'roles_verified': True,
            'edits_verified_after_reload': True, 'original_rows_forwarded': 0,
        })
        await dashboard_page()
        await self._phase('form-reload-and-resave', self.primary_pool, preference=0, fallback=0)

    @validation_test(1957, 1962)
    async def test_validation_settings_save_and_pool_role_swap(self) -> None:
        await self.primary_pool.set_available(False)
        await self._phase("fallback-before-save", self.fallback_pool, preference=0, fallback=1)
        primary, secondary, idle = self.pools.ids

        # Includes both indices just like the form, even though they did not
        # change. Reconnection is permitted; eventual correct mining is required.
        self.pools.entries[idle]["stratumUser"] += "-edited"
        await self.pools.select(primary, secondary, save_entries=True)
        await self._phase("fallback-after-settings-save", self.fallback_pool, preference=0, fallback=1)

        # Save an edited pool and the swapped role indices together. The healthy
        # endpoint becomes primary while the unavailable endpoint is fallback.
        self.pools.entries[secondary]["stratumUser"] += "-edited"
        await self.pools.select(secondary, primary, save_entries=True)
        await self._phase("edited-fallback-promoted-to-primary", self.fallback_pool, preference=0, fallback=0)

        # A preferred but unavailable fallback must still allow primary mining.
        await self._manual_select(1)
        await self._phase("unavailable-preferred-fallback", self.fallback_pool, preference=1, fallback=0)
