from __future__ import annotations

import asyncio
from typing import Any

from miner_testcode import capabilities as caps
from miner_testcode.artifacts import append_jsonl
from miner_testcode.errors import ConfigError, DeviceError
from miner_testcode.pool_fallback import (
    PoolDashboard, TemporaryPools, WorkingPool, bounded_number, wait_for_mining,
    verify_restored_mining,
)
from miner_testcode.testcase import MinerTestCase, validation_test


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

    async def _phase(self, name: str, pool: WorkingPool, *, preference: int, fallback: int) -> None:
        self.chart("Pool phase: %s", name)

        def observe(sample: dict[str, Any]) -> None:
            self.primary_pool.check_limits()
            self.fallback_pool.check_limits()
            append_jsonl(self.artifacts.path / "pool-phases.jsonl", {"phase": name, **sample})

        try:
            await wait_for_mining(self.device.current_info, pool, self.pools,
                                  preference=preference, fallback=fallback,
                                  timeout=self.phase_timeout, poll_interval=self.poll_interval,
                                  observe=observe, dashboard=self.dashboard)
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
