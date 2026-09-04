from __future__ import annotations

import asyncio
import inspect
import math
from collections.abc import Mapping
from typing import Any

from miner_testcode import capabilities as caps
from miner_testcode.devices.base import PoolSettings
from miner_testcode.interfaces.fake_stratum_v2 import (
    SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL,
    SV2_MSG_OPEN_STANDARD_MINING_CHANNEL,
    SV2_MSG_SETUP_CONNECTION,
    FakeStratumV2Server,
    StratumV2Handshake,
    Sv2MiningJob,
    Sv2ShareSubmission,
)
from miner_testcode.testcase import MinerTestCase


class StratumV2RegressionTest(MinerTestCase):
    """Exercise the device SV2 client against an authenticated local pool."""

    class_scoped_lifecycle = True
    required_capabilities = frozenset(
        {caps.API, caps.MINING_STATE, caps.POOL_CONFIG, caps.STRATUM_V2}
    )

    def _class_fixture(self) -> None:
        """Synthetic method name used for the shared artifact lifecycle."""

    @classmethod
    async def _drain_class_cleanups(cls) -> None:
        errors: list[BaseException] = []
        while cls._fixture_owner._cleanups:
            function, args, kwargs = cls._fixture_owner._cleanups.pop()
            try:
                result = function(*args, **kwargs)
                if inspect.isawaitable(result):
                    await result
            except BaseException as exc:
                errors.append(exc)
        if errors:
            raise ExceptionGroup("class-scoped Stratum V2 cleanup failed", errors)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._ordered_case_failed = False
        cls._class_runner = asyncio.Runner()
        cls._fixture_owner = cls("_class_fixture")
        cls._fixture_owner._context = cls._class_context
        try:
            cls._class_runner.run(MinerTestCase.asyncSetUp(cls._fixture_owner))
            cls._fixture_owner.chart("Stratum V2 regression suite started")
            (
                cls._server,
                cls._settings,
                cls._username,
                cls._channel_type,
            ) = cls._class_runner.run(cls._fixture_owner._start_local_pool())
        except BaseException:
            try:
                cls._class_runner.run(cls._drain_class_cleanups())
            finally:
                cls._class_runner.close()
            raise

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls._class_runner.run(cls._drain_class_cleanups())
        finally:
            cls._class_runner.close()
            super().tearDownClass()

    def setUp(self) -> None:
        super().setUp()
        if type(self)._ordered_case_failed:
            self.skipTest("an earlier ordered Stratum V2 feature failed")

    async def asyncSetUp(self) -> None:
        owner = type(self)._fixture_owner
        self._context = owner._context
        self.artifacts = owner.artifacts
        self.logger = owner.logger
        self.device = owner.device
        self.baseline = owner.baseline

    def _run_ordered_case(self, awaitable: Any) -> None:
        try:
            type(self)._class_runner.run(awaitable)
        except BaseException:
            type(self)._ordered_case_failed = True
            raise

    async def _start_local_pool(
        self,
    ) -> tuple[FakeStratumV2Server, Mapping[str, Any], str, str]:
        settings = self.settings_for("stratum_v2_regression")
        advertised_host = str(settings.get("advertised_host", "")).strip()
        if not advertised_host:
            self.fail(
                "tests.stratum_v2_regression.advertised_host must be the test "
                "host address reachable by the device"
            )
        channel_type = str(settings.get("channel_type", "extended")).strip().lower()
        if channel_type not in {"standard", "extended"}:
            self.fail(
                "tests.stratum_v2_regression.channel_type must be standard or extended"
            )
        initial_difficulty = float(settings.get("share_difficulty", 256.0))
        server = FakeStratumV2Server(
            host=str(settings.get("bind_host", "0.0.0.0")),
            port=int(settings.get("port", 0)),
            initial_difficulty=initial_difficulty,
            handshake_timeout=float(settings.get("handshake_timeout", 45.0)),
        )
        await server.start()
        self.addCleanup(
            server.write_transcript,
            self.artifacts.path / "fake-stratum-v2.jsonl",
        )
        self.addAsyncCleanup(server.close)
        self.logger.info(
            "Local authenticated Stratum V2 server listening on port %d",
            server.port,
        )

        username = str(settings.get("username", "stratum-v2-regression.worker"))
        await self.device.configure_pool(
            PoolSettings(
                host=advertised_host,
                port=server.port,
                username=username,
                tls=False,
                protocol="SV2",
                sv2_channel_type=channel_type,
                sv2_authority_pubkey=server.authority_public_key_base58,
                sv2_require_auth=True,
            )
        )
        return server, settings, username, channel_type

    @staticmethod
    def _latest_sequence(server: FakeStratumV2Server) -> int:
        return server.frames[-1].sequence if server.frames else 0

    async def _wait_for_pool_difficulty(
        self, expected: float, *, timeout: float
    ) -> None:
        async with asyncio.timeout(timeout):
            while True:
                info = await self.device.current_info()
                value = info.get("poolDifficulty")
                if value is not None and math.isclose(
                    float(value), expected, rel_tol=1e-6, abs_tol=1e-9
                ):
                    return
                await asyncio.sleep(0.25)

    async def _mine_one_share(
        self,
        server: FakeStratumV2Server,
        handshake: StratumV2Handshake,
        job: Sv2MiningJob,
        *,
        difficulty: float | None,
        timeout: float,
    ) -> Sv2ShareSubmission:
        after = self._latest_sequence(server)
        await server.send_job(
            job,
            difficulty=difficulty,
            session=handshake.connection_id,
        )
        submission = await server.wait_for_submission(
            job_id=job.job_id,
            connection_id=handshake.connection_id,
            after_sequence=after,
            timeout=timeout,
        )
        self.assertEqual(submission.channel_id, handshake.channel_id)
        self.assertGreaterEqual(submission.ntime, job.ntime)
        self.assertLessEqual(submission.nonce, 0xFFFFFFFF)
        self.assertLessEqual(submission.version, 0xFFFFFFFF)
        if handshake.open_channel.channel_type == "extended":
            self.assertIsNotNone(submission.extranonce)
            assert submission.extranonce is not None
            self.assertEqual(len(submission.extranonce), 8)
        else:
            self.assertIsNone(submission.extranonce)
        return submission

    async def _case_01_noise_handshake(
        self,
        server: FakeStratumV2Server,
        settings: Mapping[str, Any],
    ) -> None:
        session = await server.wait_for_noise_handshake(
            timeout=float(settings.get("handshake_timeout", 45.0))
        )
        self.assertIsNotNone(session.noise)
        self.assertGreater(len(server.authority_public_key_base58), 40)
        self.logger.info("Authenticated Noise NX transport completed")

    async def _case_02_setup_connection(
        self,
        server: FakeStratumV2Server,
        settings: Mapping[str, Any],
        channel_type: str,
    ) -> None:
        request = await server.wait_for_frame(
            SV2_MSG_SETUP_CONNECTION,
            timeout=float(settings.get("handshake_timeout", 45.0)),
        )
        self.assertEqual(request.decoded["protocol"], 0)
        self.assertLessEqual(int(request.decoded["min_version"]), 2)
        self.assertGreaterEqual(int(request.decoded["max_version"]), 2)
        expected_flag = 1 if channel_type == "standard" else 0
        self.assertEqual(int(request.decoded["flags"]) & 1, expected_flag)
        self.logger.info("SetupConnection negotiated SV2 mining protocol version 2")

    async def _case_03_open_mining_channel(
        self,
        server: FakeStratumV2Server,
        settings: Mapping[str, Any],
        username: str,
        channel_type: str,
    ) -> StratumV2Handshake:
        connection_id = max(
            (session.connection_id for session in server.sessions),
            default=None,
        )
        self.assertIsNotNone(connection_id)
        handshake = await server.wait_for_handshake(
            connection_id=connection_id,
            timeout=float(settings.get("handshake_timeout", 45.0))
        )
        expected_message = (
            SV2_MSG_OPEN_STANDARD_MINING_CHANNEL
            if channel_type == "standard"
            else SV2_MSG_OPEN_EXTENDED_MINING_CHANNEL
        )
        request = await server.wait_for_frame(
            expected_message,
            connection_id=handshake.connection_id,
            timeout=float(settings.get("handshake_timeout", 45.0)),
        )
        self.assertEqual(handshake.open_channel.channel_type, channel_type)
        self.assertEqual(handshake.open_channel.user_identity, username)
        self.assertGreater(handshake.open_channel.nominal_hash_rate, 0)
        self.assertEqual(request.decoded["channel_type"], channel_type)
        self.logger.info("Opened %s SV2 mining channel", channel_type)
        return handshake

    async def _case_04_future_job_and_accepted_share(
        self,
        server: FakeStratumV2Server,
        handshake: StratumV2Handshake,
        settings: Mapping[str, Any],
    ) -> None:
        difficulty = float(settings.get("share_difficulty", 256.0))
        share_timeout = float(settings.get("share_timeout", 45.0))
        accept_timeout = float(settings.get("accept_timeout", 20.0))
        accepted_before = self.device.state.latest.shares_accepted
        generation = self.device.state.generation
        job = Sv2MiningJob.standard(1_001)
        server.submission_policy = lambda submission: submission.job_id == job.job_id
        await self._mine_one_share(
            server,
            handshake,
            job,
            difficulty=None,
            timeout=share_timeout,
        )
        await self._wait_for_pool_difficulty(difficulty, timeout=accept_timeout)
        await self.device.state.wait_for(
            lambda state: state.online and state.shares_accepted > accepted_before,
            timeout=accept_timeout,
            description="the SV2 accepted-share response",
            after_generation=generation,
        )
        self.logger.info("Future job activation produced an accepted SV2 share")

    async def _case_05_target_change_and_fresh_work(
        self,
        server: FakeStratumV2Server,
        handshake: StratumV2Handshake,
        settings: Mapping[str, Any],
    ) -> None:
        initial = float(settings.get("share_difficulty", 256.0))
        changed = float(settings.get("changed_difficulty", initial * 2.0))
        self.assertGreater(initial, 0)
        self.assertGreater(changed, 0)
        self.assertNotEqual(changed, initial)
        accept_timeout = float(settings.get("accept_timeout", 20.0))
        share_timeout = float(settings.get("share_timeout", 45.0))

        await server.send_target(changed, session=handshake.connection_id)
        await self._wait_for_pool_difficulty(changed, timeout=accept_timeout)
        accepted_before = self.device.state.latest.shares_accepted
        generation = self.device.state.generation
        job = Sv2MiningJob.standard(1_002)
        server.submission_policy = lambda submission: submission.job_id == job.job_id
        await self._mine_one_share(
            server,
            handshake,
            job,
            difficulty=None,
            timeout=share_timeout,
        )
        await self.device.state.wait_for(
            lambda state: state.online and state.shares_accepted > accepted_before,
            timeout=accept_timeout,
            description="the changed-target SV2 accepted-share response",
            after_generation=generation,
        )
        self.logger.info("SetTarget changed difficulty and fresh work remained live")

    async def _case_06_rejected_share(
        self,
        server: FakeStratumV2Server,
        handshake: StratumV2Handshake,
        settings: Mapping[str, Any],
    ) -> None:
        share_timeout = float(settings.get("share_timeout", 45.0))
        accept_timeout = float(settings.get("accept_timeout", 20.0))
        rejected_before = self.device.state.latest.shares_rejected
        generation = self.device.state.generation
        job = Sv2MiningJob.standard(1_003)
        server.submission_policy = lambda submission: submission.job_id != job.job_id
        await self._mine_one_share(
            server,
            handshake,
            job,
            difficulty=None,
            timeout=share_timeout,
        )
        await self.device.state.wait_for(
            lambda state: state.online and state.shares_rejected > rejected_before,
            timeout=accept_timeout,
            description="the SV2 rejected-share response",
            after_generation=generation,
        )
        self.logger.info("SubmitShares.Error reached device rejected-share state")

    async def _case_07_reconnect_and_fresh_share(
        self,
        server: FakeStratumV2Server,
        handshake: StratumV2Handshake,
        settings: Mapping[str, Any],
        username: str,
        channel_type: str,
    ) -> StratumV2Handshake:
        await server.disconnect(handshake.connection_id)
        reconnected = await server.wait_for_handshake(
            after_connection_id=handshake.connection_id,
            timeout=float(settings.get("reconnect_timeout", 45.0)),
        )
        self.assertEqual(reconnected.open_channel.user_identity, username)
        self.assertEqual(reconnected.open_channel.channel_type, channel_type)
        accepted_before = self.device.state.latest.shares_accepted
        generation = self.device.state.generation
        job = Sv2MiningJob.standard(1_004)
        server.submission_policy = lambda submission: submission.job_id == job.job_id
        await self._mine_one_share(
            server,
            reconnected,
            job,
            difficulty=None,
            timeout=float(settings.get("share_timeout", 45.0)),
        )
        await self.device.state.wait_for(
            lambda state: state.online and state.shares_accepted > accepted_before,
            timeout=float(settings.get("accept_timeout", 20.0)),
            description="the post-reconnect SV2 accepted-share response",
            after_generation=generation,
        )
        self.logger.info("Reconnected through Noise and submitted fresh SV2 work")
        return reconnected

    def test_01_noise_handshake(self) -> None:
        self._run_ordered_case(
            self._case_01_noise_handshake(type(self)._server, type(self)._settings)
        )

    def test_02_setup_connection(self) -> None:
        self._run_ordered_case(
            self._case_02_setup_connection(
                type(self)._server,
                type(self)._settings,
                type(self)._channel_type,
            )
        )

    def test_03_open_mining_channel(self) -> None:
        async def run() -> None:
            type(self)._handshake = await self._case_03_open_mining_channel(
                type(self)._server,
                type(self)._settings,
                type(self)._username,
                type(self)._channel_type,
            )

        self._run_ordered_case(run())

    def test_04_future_job_and_accepted_share(self) -> None:
        self._run_ordered_case(
            self._case_04_future_job_and_accepted_share(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
            )
        )

    def test_05_target_change_and_fresh_work(self) -> None:
        self._run_ordered_case(
            self._case_05_target_change_and_fresh_work(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
            )
        )

    def test_06_rejected_share(self) -> None:
        self._run_ordered_case(
            self._case_06_rejected_share(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
            )
        )

    def test_07_reconnect_and_fresh_share(self) -> None:
        async def run() -> None:
            type(self)._handshake = await self._case_07_reconnect_and_fresh_share(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
                type(self)._username,
                type(self)._channel_type,
            )

        self._run_ordered_case(run())
