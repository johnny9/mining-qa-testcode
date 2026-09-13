from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
from collections.abc import Mapping
from typing import Any

from miner_testcode import capabilities as caps
from miner_testcode.devices.base import PoolSettings
from miner_testcode.interfaces.fake_stratum import (
    STRATUM_V1_MAX_JSON_LINE_SIZE,
    FakeStratumV1Server,
    MiningJob,
    ShareSubmission,
    StratumHandshake,
)
from miner_testcode.testcase import MinerTestCase, validation_test


class StratumV1RegressionTest(MinerTestCase):
    """Exercise the device Stratum client against a scriptable local pool."""

    class_scoped_lifecycle = True
    required_capabilities = frozenset(
        {caps.API, caps.MINING_STATE, caps.POOL_CONFIG, caps.STRATUM_V1}
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
            raise ExceptionGroup("class-scoped Stratum cleanup failed", errors)

    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls._ordered_case_failed = False
        cls._class_runner = asyncio.Runner()
        cls._fixture_owner = cls("_class_fixture")
        cls._fixture_owner._context = cls._class_context
        try:
            cls._class_runner.run(
                MinerTestCase.asyncSetUp(cls._fixture_owner)
            )
            cls._fixture_owner.chart("Stratum V1 regression suite started")
            (
                cls._server,
                cls._settings,
                cls._username,
            ) = cls._class_runner.run(
                cls._fixture_owner._start_local_pool()
            )
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
            self.skipTest("an earlier ordered Stratum feature failed")

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
    ) -> tuple[FakeStratumV1Server, Mapping[str, Any], str]:
        settings = self.settings_for("stratum_v1_regression")
        self._max_ntime_roll_seconds()
        advertised_host = str(settings.get("advertised_host", "")).strip()
        if not advertised_host:
            self.fail(
                "tests.stratum_v1_regression.advertised_host must be the test "
                "host address reachable by the device"
            )

        server = FakeStratumV1Server(
            host=str(settings.get("bind_host", "0.0.0.0")),
            port=int(settings.get("port", 0)),
            extranonce1=str(settings.get("extranonce1", "01020304050607")),
            extranonce2_size=int(settings.get("extranonce2_size", 8)),
            version_mask=str(settings.get("version_mask", "1fffe000")),
        )
        await server.start()
        # Close first, then serialize all final disconnect events.  The generic
        # device cleanup subsequently restores the real pool configuration.
        self.addCleanup(
            server.write_transcript, self.artifacts.path / "fake-stratum.jsonl"
        )
        self.addAsyncCleanup(server.close)
        self.logger.info("Local Stratum server listening on port %d", server.port)

        username = str(settings.get("username", "stratum-regression.worker"))
        password_env = settings.get("temporary_password_env")
        if password_env is not None:
            password = os.environ.get(str(password_env))
            if password is None:
                self.fail(f"temporary password variable {password_env} is not set")
        else:
            password = None
            if not bool(settings.get("allow_existing_device_password", False)):
                self.fail(
                    "set tests.stratum_v1_regression.allow_existing_device_password=true "
                    "to let the device send its current write-only pool password to "
                    "this local process, or configure temporary_password_env together "
                    "with devices.options.baseline_stratum_password_env"
                )
        await self.device.configure_pool(
            PoolSettings(
                host=advertised_host,
                port=server.port,
                username=username,
                password=password,
                tls=False,
            )
        )
        return server, settings, username

    async def _wait_for_handshake(
        self,
        server: FakeStratumV1Server,
        settings: Mapping[str, Any],
        username: str,
    ) -> StratumHandshake:
        timeout = float(settings.get("handshake_timeout", 45.0))
        after_connection = 0
        async with asyncio.timeout(timeout):
            while True:
                # Settings can reconnect the old boot just before the adapter
                # restarts it. That socket may appear open until our first
                # write; select the newest session and prove it responds.
                candidates = [s for s in server.sessions
                              if s.connected and s.connection_id > after_connection]
                session = (max(candidates, key=lambda s: s.connection_id) if candidates else
                           await server.wait_for_connection(after_connection_id=after_connection,
                                                            timeout=timeout))
                after_connection = session.connection_id
                handshake = await server.wait_for_handshake(
                    connection_id=session.connection_id, require_configure=True, timeout=timeout)
                try:
                    await self._processing_barrier(
                        server, session.connection_id, 10_000 + session.connection_id,
                        timeout=min(2.0, timeout / 4))
                except (ConnectionError, TimeoutError):
                    continue
                break
        authorize_params = handshake.authorize.params
        self.assertIsNotNone(authorize_params)
        assert authorize_params is not None
        self.assertEqual(authorize_params[0], username)
        return handshake

    @staticmethod
    def _latest_sequence(server: FakeStratumV1Server) -> int:
        return server.requests[-1].sequence if server.requests else 0

    async def _processing_barrier(
        self,
        server: FakeStratumV1Server,
        connection_id: int,
        barrier_id: int,
        *,
        timeout: float = 10.0,
    ) -> None:
        after = self._latest_sequence(server)
        await server.send_json(
            {"id": barrier_id, "method": "mining.ping", "params": []},
            session=connection_id,
            label=f"barrier:{barrier_id}",
        )
        await server.wait_for_request(
            "pong",
            connection_id=connection_id,
            after_sequence=after,
            predicate=lambda request: request.message_id == barrier_id,
            timeout=timeout,
        )

    def _max_ntime_roll_seconds(self) -> int:
        value = self.settings_for("stratum_v1_regression").get("max_ntime_roll_seconds", 0)
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 120:
            raise ValueError("max_ntime_roll_seconds must be an integer from 0 to 120")
        return value

    def _assert_submission_ntime(self, submitted: str, job_ntime: str) -> None:
        self.assertRegex(submitted, r"^[0-9a-fA-F]{8}$")
        offset = int(submitted, 16) - int(job_ntime, 16)
        self.assertGreaterEqual(offset, 0, "share timestamp predates its job")
        self.assertLessEqual(offset, self._max_ntime_roll_seconds(),
                             "share timestamp exceeds configured rolling allowance")

    async def _mine_one_share(
        self,
        server: FakeStratumV1Server,
        job: MiningJob,
        *,
        difficulty: float | None,
        connection_id: int,
        timeout: float,
        fragment_sizes: tuple[int, ...] | None = None,
        fragment_delay: float = 0.0,
    ) -> ShareSubmission:
        after = self._latest_sequence(server)
        await server.send_job(
            job,
            difficulty=difficulty,
            session=connection_id,
            fragment_sizes=fragment_sizes,
            fragment_delay=fragment_delay,
        )
        submission = await server.wait_for_submission(
            job_id=job.job_id,
            connection_id=connection_id,
            after_sequence=after,
            timeout=timeout,
        )
        self._assert_submission_ntime(submission.ntime, job.ntime)
        self.assertRegex(submission.extranonce2, r"^[0-9a-fA-F]*$")
        self.assertRegex(submission.nonce, r"^[0-9a-fA-F]{8}$")
        if submission.version_bits is not None:
            self.assertRegex(submission.version_bits, r"^[0-9a-fA-F]{8}$")
        return submission

    async def _park_work(
        self,
        server: FakeStratumV1Server,
        connection_id: int,
        sequence: int,
    ) -> None:
        await server.send_job(
            MiningJob.standard(f"park-{sequence}"),
            difficulty=float(0xffffffff),
            session=connection_id,
        )
        await self._processing_barrier(
            server, connection_id, 80_000 + sequence
        )

    async def _wait_for_pool_difficulty(
        self, expected: float, *, timeout: float
    ) -> None:
        async with asyncio.timeout(timeout):
            while True:
                info = await self.device.current_info()
                value = info.get("poolDifficulty")
                if value is not None and float(value) == expected:
                    return
                await asyncio.sleep(0.25)

    async def _reconnect_with_configure_response(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
        *,
        configure_response: bool | None,
    ) -> StratumHandshake:
        server.configure_response = configure_response
        previous_connection = handshake.connection_id
        await server.send_notification(
            "client.reconnect", [], session=previous_connection
        )
        return await server.wait_for_handshake(
            after_connection_id=previous_connection,
            require_configure=True,
            timeout=float(settings.get("reconnect_timeout", 45.0)),
        )

    async def _case_01_configure_extension_negotiation(
        self,
        server: FakeStratumV1Server,
        settings: Mapping[str, Any],
    ) -> None:
        type(self)._handshake = await self._wait_for_handshake(
            server, settings, type(self)._username)
        request = type(self)._handshake.configure
        self.assertIsNotNone(request)
        assert request is not None
        self.assertIsNotNone(request.params)
        assert request.params is not None
        self.assertGreaterEqual(len(request.params), 1)
        self.assertIsInstance(request.params[0], list)
        self.assertIn("version-rolling", request.params[0])
        self.logger.info("mining.configure negotiated version rolling")

    async def _case_02_subscribe_request(
        self,
        server: FakeStratumV1Server,
        settings: Mapping[str, Any],
    ) -> None:
        request = type(self)._handshake.subscribe
        self.assertIsNotNone(request.params)
        assert request.params is not None
        self.assertGreaterEqual(len(request.params), 1)
        self.assertIsInstance(request.params[0], str)
        self.assertTrue(request.params[0])
        self.logger.info("mining.subscribe completed")

    async def _case_03_authorize_request(
        self,
        server: FakeStratumV1Server,
        settings: Mapping[str, Any],
        username: str,
    ) -> StratumHandshake:
        request = type(self)._handshake.authorize
        self.assertIsNotNone(request.params)
        assert request.params is not None
        self.assertGreaterEqual(len(request.params), 2)
        self.assertEqual(request.params[0], username)
        self.assertEqual(request.params[1], "<redacted>")
        self.logger.info("mining.authorize completed")
        return type(self)._handshake

    async def _case_04_mining_notify_and_accepted_share(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
        username: str,
    ) -> None:
        difficulty = float(settings.get("share_difficulty", 256.0))
        share_timeout = float(settings.get("share_timeout", 45.0))
        accept_timeout = float(settings.get("accept_timeout", 20.0))
        expected_extranonce2_chars = server.extranonce2_size * 2
        self.assertGreater(difficulty, 0)
        accepted_before = self.device.state.latest.shares_accepted

        job = MiningJob.standard("basic-mining-notify")
        server.submission_policy = lambda submission: submission.job_id == job.job_id
        submission = await self._mine_one_share(
            server,
            job,
            difficulty=difficulty,
            connection_id=handshake.connection_id,
            timeout=share_timeout,
        )
        self.assertEqual(submission.username, username)
        self.assertEqual(
            len(submission.extranonce2), expected_extranonce2_chars
        )
        await self._wait_for_pool_difficulty(difficulty, timeout=accept_timeout)
        self.logger.info("mining.notify produced a valid share")

        generation = self.device.state.generation
        await self.device.state.wait_for(
            lambda state: state.online and state.shares_accepted > accepted_before,
            timeout=accept_timeout,
            description="the fake-pool accepted-share response",
            after_generation=generation,
        )
        self.logger.info("Accepted share reached device state")

    async def _case_05_difficulty_change_and_fresh_work(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
        username: str,
    ) -> None:
        initial_difficulty = float(settings.get("share_difficulty", 256.0))
        changed_difficulty = float(
            settings.get("changed_difficulty", initial_difficulty * 2.0)
        )
        share_timeout = float(settings.get("share_timeout", 45.0))
        accept_timeout = float(settings.get("accept_timeout", 20.0))
        self.assertGreater(initial_difficulty, 0)
        self.assertGreater(changed_difficulty, 0)
        self.assertNotEqual(changed_difficulty, initial_difficulty)

        job = MiningJob.standard("work-after-difficulty")
        server.submission_policy = lambda submission: submission.job_id == job.job_id
        await server.send_difficulty(
            initial_difficulty, session=handshake.connection_id
        )
        await self._wait_for_pool_difficulty(
            initial_difficulty, timeout=accept_timeout
        )
        await server.send_difficulty(
            changed_difficulty, session=handshake.connection_id
        )
        await self._wait_for_pool_difficulty(
            changed_difficulty, timeout=accept_timeout
        )
        self.logger.info("mining.set_difficulty changed the device pool target")

        accepted_before = self.device.state.latest.shares_accepted
        submission = await self._mine_one_share(
            server,
            job,
            difficulty=None,
            connection_id=handshake.connection_id,
            timeout=share_timeout,
        )
        self.assertEqual(submission.username, username)
        self.logger.info(
            "Fresh mining.notify used the changed difficulty and produced a share"
        )

        generation = self.device.state.generation
        await self.device.state.wait_for(
            lambda state: state.online and state.shares_accepted > accepted_before,
            timeout=accept_timeout,
            description="the changed-difficulty accepted-share response",
            after_generation=generation,
        )
        self.logger.info("Changed-difficulty share reached device state")

    def test_01_configure_extension_negotiation(self) -> None:
        self._run_ordered_case(
            self._case_01_configure_extension_negotiation(
                type(self)._server, type(self)._settings
            )
        )

    def test_02_subscribe_request(self) -> None:
        self._run_ordered_case(
            self._case_02_subscribe_request(
                type(self)._server, type(self)._settings
            )
        )

    def test_03_authorize_request(self) -> None:
        async def run() -> None:
            type(self)._handshake = await self._case_03_authorize_request(
                type(self)._server,
                type(self)._settings,
                type(self)._username,
            )

        self._run_ordered_case(run())

    def test_04_mining_notify_and_accepted_share(self) -> None:
        self._run_ordered_case(
            self._case_04_mining_notify_and_accepted_share(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
                type(self)._username,
            )
        )

    def test_05_difficulty_change_and_fresh_work(self) -> None:
        self._run_ordered_case(
            self._case_05_difficulty_change_and_fresh_work(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
                type(self)._username,
            )
        )

    async def _case_90_fragmented_consecutive_and_boundary_messages(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
    ) -> StratumHandshake:
        difficulty = float(settings.get("share_difficulty", 256.0))
        timeout = float(settings.get("share_timeout", 45.0))
        connection_id = handshake.connection_id

        fragmented = MiningJob.standard("fragmented-notify")
        await self._mine_one_share(
            server,
            fragmented,
            difficulty=difficulty,
            connection_id=connection_id,
            timeout=timeout,
            fragment_sizes=(1, 2, 3, 5, 8, 13, 21, 34),
            fragment_delay=0.01,
        )
        self.logger.info("Fragmented JSON-RPC line produced valid work")

        consecutive = MiningJob.standard("consecutive-notify")
        after = self._latest_sequence(server)
        await server.send_batch(
            [
                {
                    "id": None,
                    "method": "mining.set_difficulty",
                    "params": [difficulty],
                },
                consecutive.notification(),
            ],
            session=connection_id,
            label="consecutive-difficulty-and-notify",
        )
        await server.wait_for_submission(
            job_id=consecutive.job_id,
            connection_id=connection_id,
            after_sequence=after,
            timeout=timeout,
        )
        self.logger.info("Consecutive JSON-RPC lines were both processed")

        boundary = MiningJob.standard("boundary-successor")
        maximum_object = b"{}" + b" " * (STRATUM_V1_MAX_JSON_LINE_SIZE - 2)
        notify_line = json.dumps(
            boundary.notification(), separators=(",", ":")
        ).encode("utf-8")
        after = self._latest_sequence(server)
        await server.send_raw(
            maximum_object + b"\n" + notify_line + b"\n",
            session=connection_id,
            label="maximum-line-and-successor",
        )
        await server.wait_for_submission(
            job_id=boundary.job_id,
            connection_id=connection_id,
            after_sequence=after,
            timeout=timeout,
        )
        self.logger.info("16 KiB line preserved and processed its successor")

        for label, invalid_bytes in (
            ("embedded NUL", b"{}\x00\n"),
            ("oversized line", b" " * (STRATUM_V1_MAX_JSON_LINE_SIZE + 1) + b"\n"),
        ):
            previous_connection = connection_id
            await server.send_raw(
                invalid_bytes,
                session=previous_connection,
                label=label.lower().replace(" ", "-"),
            )
            recovered = await server.wait_for_handshake(
                after_connection_id=previous_connection,
                require_configure=True,
                timeout=float(settings.get("reconnect_timeout", 45.0)),
            )
            handshake = recovered
            connection_id = recovered.connection_id
            recovery_job = MiningJob.standard(
                f"recovery-{label.lower().replace(' ', '-')}"
            )
            await self._mine_one_share(
                server,
                recovery_job,
                difficulty=difficulty,
                connection_id=connection_id,
                timeout=timeout,
            )
            self.logger.info("Recovered after %s", label)
        return handshake

    async def _case_91_invalid_messages_do_not_create_work_or_corrupt_state(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
    ) -> None:
        difficulty = float(settings.get("share_difficulty", 256.0))
        timeout = float(settings.get("share_timeout", 45.0))
        no_submit_window = float(settings.get("invalid_submit_window", 0.1))
        connection_id = handshake.connection_id
        expected_extranonce2_chars = server.extranonce2_size * 2
        barrier = 90_000

        valid = MiningJob.standard("invalid-template")
        initial_info = await self.device.current_info()
        self.assertIn(
            "workReceived",
            initial_info,
            "target firmware must expose workReceived for side-effect assertions",
        )
        notify_cases: list[tuple[str, dict[str, Any]]] = []

        def changed_notify(name: str, index: int, value: Any) -> None:
            payload = valid.with_changes(job_id=f"bad-{name}").notification()
            payload["params"][index] = value
            notify_cases.append((name, payload))

        changed_notify("prevhash-type", 1, 7)
        changed_notify("nonhex-prevhash", 1, "gg" * 32)
        changed_notify("short-prevhash", 1, "00" * 31)
        changed_notify("invalid-merkle", 4, ["xyz"])
        changed_notify("too-many-merkle", 4, ["00" * 32] * 33)
        changed_notify("short-version", 5, "20")
        changed_notify("short-nbits", 6, "1d00ff")
        changed_notify("short-ntime", 7, "000000")
        changed_notify("odd-coinbase", 2, valid.coinbase_1 + "f")
        changed_notify("empty-coinbase", 2, "")
        changed_notify("clean-jobs-type", 8, "true")
        changed_notify("missing-locktime", 3, valid.coinbase_2[:-8])
        changed_notify("extra-locktime", 3, valid.coinbase_2 + "00")

        for index, (name, payload) in enumerate(notify_cases, start=1):
            before = await self.device.current_info()
            work_before = int(before.get("workReceived") or 0)
            after = self._latest_sequence(server)
            await server.send_json(
                payload,
                session=connection_id,
                label=f"invalid-notify:{name}",
            )
            barrier += 1
            await self._processing_barrier(server, connection_id, barrier)
            await server.assert_no_submission(
                job_id=str(payload["params"][0]),
                after_sequence=after,
                duration=no_submit_window,
            )
            work_after = int(
                (await self.device.current_info()).get("workReceived") or 0
            )
            self.assertEqual(
                work_after,
                work_before,
                f"invalid {name} notification changed workReceived",
            )

            recovery = MiningJob.standard(f"notify-ok-{index}")
            submission = await self._mine_one_share(
                server,
                recovery,
                difficulty=difficulty,
                connection_id=connection_id,
                timeout=timeout,
            )
            self.assertEqual(
                len(submission.extranonce2), expected_extranonce2_chars
            )
            await self._park_work(server, connection_id, index)
            self.logger.info("Rejected %s and accepted successor", name)

        state_cases: list[tuple[str, bytes]] = [
            ("non-object", b"[]\n"),
            ("trailing-json", b'{"id":1,"result":true} trailing\n'),
            (
                "fractional-id",
                b'{"id":1.5,"method":"mining.set_difficulty","params":[1]}\n',
            ),
            (
                "zero-difficulty",
                b'{"id":null,"method":"mining.set_difficulty","params":[0]}\n',
            ),
            (
                "negative-extranonce2",
                b'{"id":1,"method":"mining.set_extranonce","params":["deadbeef",-1]}\n',
            ),
            (
                "oversized-extranonce2",
                b'{"id":1,"method":"mining.set_extranonce","params":["deadbeef",33]}\n',
            ),
            (
                "fractional-extranonce2",
                b'{"id":1,"method":"mining.set_extranonce","params":["deadbeef",1.5]}\n',
            ),
            (
                "malformed-subscribe-result",
                b'{"result":[[],"deadbeef",-1],"id":2,"error":null}\n',
            ),
        ]

        for offset, (name, payload) in enumerate(state_cases, start=1):
            state_before = await self.device.current_info()
            work_before = int(state_before.get("workReceived") or 0)
            difficulty_before = float(state_before.get("poolDifficulty") or 0)
            await server.send_raw(
                payload,
                session=connection_id,
                label=f"invalid-message:{name}",
            )
            barrier += 1
            await self._processing_barrier(server, connection_id, barrier)
            state_after = await self.device.current_info()
            work_after = int(state_after.get("workReceived") or 0)
            self.assertEqual(work_after, work_before)
            if name in {"fractional-id", "zero-difficulty"}:
                self.assertEqual(
                    float(state_after.get("poolDifficulty") or 0),
                    difficulty_before,
                    f"invalid {name} changed pool difficulty",
                )

            recovery = MiningJob.standard(f"state-ok-{offset}")
            submission = await self._mine_one_share(
                server,
                recovery,
                difficulty=difficulty,
                connection_id=connection_id,
                timeout=timeout,
            )
            self.assertEqual(
                len(submission.extranonce2), expected_extranonce2_chars
            )
            await self._park_work(server, connection_id, 100 + offset)
            self.logger.info("State survived %s", name)

    async def _case_92_version_rolling_requires_accepted_configure(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
    ) -> StratumHandshake:
        difficulty = float(settings.get("share_difficulty", 256.0))
        timeout = float(settings.get("share_timeout", 45.0))

        deferred = await self._reconnect_with_configure_response(
            server,
            handshake,
            settings,
            configure_response=None,
        )
        server.submission_policy = None
        await self._processing_barrier(server, deferred.connection_id, 92_000)
        before_accept = await self._mine_one_share(
            server,
            MiningJob.standard("configure-deferred"),
            difficulty=difficulty,
            connection_id=deferred.connection_id,
            timeout=timeout,
        )
        self.assertIsNone(
            before_accept.version_bits,
            "the miner submitted version bits before BIP310 was accepted",
        )

        self.assertIsNotNone(deferred.configure)
        assert deferred.configure is not None
        await server.send_configure_response(
            deferred.configure.message_id,
            accepted=True,
            session=deferred.connection_id,
        )
        await self._processing_barrier(server, deferred.connection_id, 92_001)
        after_accept = await self._mine_one_share(
            server,
            MiningJob.standard("configure-accepted").with_changes(version="20002000"),
            difficulty=difficulty,
            connection_id=deferred.connection_id,
            timeout=timeout,
        )
        self.assertIsNotNone(
            after_accept.version_bits,
            "the miner did not submit negotiated BIP310 version bits",
        )
        assert after_accept.version_bits is not None
        self.assertEqual(
            int(after_accept.version_bits, 16) & ~int(server.version_mask, 16),
            0,
            "submitted version bits exceed the negotiated mask",
        )

        rejected = await self._reconnect_with_configure_response(
            server,
            deferred,
            settings,
            configure_response=False,
        )
        await self._processing_barrier(server, rejected.connection_id, 92_002)
        after_reject = await self._mine_one_share(
            server,
            MiningJob.standard("configure-rejected"),
            difficulty=difficulty,
            connection_id=rejected.connection_id,
            timeout=timeout,
        )
        self.assertIsNone(
            after_reject.version_bits,
            "the miner submitted version bits after BIP310 was rejected",
        )
        self.logger.info("BIP310 version rolling stayed gated by configure acceptance")
        return rejected

    async def _case_93_zero_length_extranonce2_produces_work(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
    ) -> None:
        difficulty = float(settings.get("share_difficulty", 256.0))
        timeout = float(settings.get("share_timeout", 45.0))
        accept_timeout = float(settings.get("accept_timeout", 20.0))
        connection_id = handshake.connection_id

        # With both extranonce2 and version rolling disabled, a random job's
        # finite nonce/ntime space may contain no difficulty-256 solution.
        # Find one first, then preserve its exact coinbase and block version
        # while moving the solved extranonce2 bytes into the fixed suffix.
        seed = MiningJob.standard("zero-extranonce-seed")
        solution = await self._mine_one_share(
            server, seed, difficulty=difficulty,
            connection_id=connection_id, timeout=timeout,
        )
        self.assertIsNone(solution.version_bits)
        job = seed.with_fixed_extranonce2(solution.extranonce2).with_changes(
            job_id="zero-length-extranonce2", ntime=solution.ntime,
        )
        await server.send_notification(
            "mining.set_extranonce",
            [server.extranonce1, 0],
            session=connection_id,
        )
        await self._processing_barrier(server, connection_id, 93_001)
        accepted_before = self.device.state.latest.shares_accepted
        generation = self.device.state.generation
        server.submission_policy = lambda submission: submission.job_id == job.job_id
        try:
            submission = await self._mine_one_share(
                server,
                job,
                difficulty=difficulty,
                connection_id=connection_id,
                timeout=timeout,
            )
            self.assertEqual(submission.extranonce2, "")
            await self.device.state.wait_for(
                lambda state: state.online
                and state.shares_accepted > accepted_before,
                timeout=accept_timeout,
                description="an accepted zero-length-extranonce2 share",
                after_generation=generation,
            )
        finally:
            await server.send_notification(
                "mining.set_extranonce",
                [server.extranonce1, server.extranonce2_size],
                session=connection_id,
            )
            await self._processing_barrier(server, connection_id, 93_002)
            server.submission_policy = None
        self.logger.info("Zero-length extranonce2 produced accepted work")

    async def _case_94_healthy_client_reconnects_reset_retry_history(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
    ) -> StratumHandshake:
        difficulty = float(settings.get("share_difficulty", 256.0))
        timeout = float(settings.get("share_timeout", 45.0))
        cycles = int(settings.get("healthy_reconnect_cycles", 3))
        self.assertGreaterEqual(cycles, 3)
        self.assertLessEqual(cycles, 10)
        server.configure_response = True
        server.submission_policy = None

        current = handshake
        for cycle in range(1, cycles + 1):
            current = await self._reconnect_with_configure_response(
                server,
                current,
                settings,
                configure_response=True,
            )
            await self._processing_barrier(
                server, current.connection_id, 94_000 + cycle
            )
            job = MiningJob.standard(f"healthy-reconnect-{cycle}")
            submission = await self._mine_one_share(
                server,
                job,
                difficulty=difficulty,
                connection_id=current.connection_id,
                timeout=timeout,
            )
            self.assertEqual(submission.job_id, job.job_id)
            self.logger.info("Healthy reconnect cycle %d/%d mined", cycle, cycles)
        return current

    async def _case_95_oversized_jobs_are_rejected_without_state_change(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
    ) -> None:
        difficulty = float(settings.get("share_difficulty", 256.0))
        timeout = float(settings.get("share_timeout", 45.0))
        no_submit_window = float(settings.get("invalid_submit_window", 0.1))
        connection_id = handshake.connection_id
        template = MiningJob.standard("oversized-template")
        server.submission_policy = None
        # Malformed notifications intentionally bypass MiningJob's valid-ID
        # constructor bound, as the parser tests above bypass other fields.
        cases = (
            {0: "j" * 512},
            {0: "oversized-coinbase-prefix", 2: "00" * 4096},
            {0: "malformed-large-suffix", 3: "00" * 4096},
        )

        for index, changes in enumerate(cases, start=1):
            invalid = template.notification()
            for field, value in changes.items():
                invalid["params"][field] = value
            before = await self.device.current_info()
            self.assertIn("workReceived", before)
            work_before = int(before.get("workReceived") or 0)
            after = self._latest_sequence(server)
            await server.send_json(invalid, session=connection_id, label="invalid-notify")
            await self._processing_barrier(
                server, connection_id, 95_000 + index
            )
            await server.assert_no_submission(
                job_id=invalid["params"][0],
                after_sequence=after,
                duration=no_submit_window,
            )
            work_after = int(
                (await self.device.current_info()).get("workReceived") or 0
            )
            self.assertEqual(
                work_after,
                work_before,
                "an oversized or malformed job was accepted or silently truncated",
            )

            recovery = MiningJob.standard(f"valid-after-oversized-{index}")
            await self._mine_one_share(
                server,
                recovery,
                difficulty=difficulty,
                connection_id=connection_id,
                timeout=timeout,
            )
        # 4096 bytes are below the firmware suffix capacity. Prove that size
        # alone does not reject a structurally valid multi-payout-capable job.
        prefix = bytes.fromhex(template.coinbase_1)
        script_tail = 42 + prefix[41] - len(prefix) - len(server.extranonce1) // 2 - server.extranonce2_size
        suffix = (bytes.fromhex(template.coinbase_2)[:script_tail + 4]
                  + b"\x01" + bytes(8) + b"\xfd\x00\x10"
                  + b"\x6a" + bytes(4095) + bytes(4))
        await self._mine_one_share(
            server, template.with_changes(job_id="large-valid-suffix", coinbase_2=suffix.hex()),
            difficulty=difficulty, connection_id=connection_id, timeout=timeout,
        )
        self.logger.info("Oversized/malformed jobs were rejected and a valid large suffix mined")

    async def _case_96_burst_keeps_latest_clean_job_valid(
        self,
        server: FakeStratumV1Server,
        handshake: StratumHandshake,
        settings: Mapping[str, Any],
    ) -> None:
        difficulty = float(settings.get("share_difficulty", 256.0))
        timeout = float(settings.get("share_timeout", 45.0))
        burst_jobs = int(settings.get("job_burst_count", 24))
        self.assertGreaterEqual(burst_jobs, 12)
        self.assertLessEqual(burst_jobs, 64)
        connection_id = handshake.connection_id
        base_ntime = int(time.time()) & 0xFFFFFFFF
        jobs = [
            MiningJob.standard(
                f"burst-{index:02d}", clean_jobs=index == burst_jobs - 1
            ).with_changes(ntime=f"{(base_ntime + index) & 0xFFFFFFFF:08x}")
            for index in range(burst_jobs)
        ]
        final = jobs[-1]
        server.submission_policy = lambda submission: submission.job_id == final.job_id
        after = self._latest_sequence(server)
        await server.send_batch(
            [
                {
                    "id": None,
                    "method": "mining.set_difficulty",
                    "params": [difficulty],
                },
                *(job.notification() for job in jobs),
            ],
            session=connection_id,
            label=f"job-burst:{burst_jobs}",
        )
        submission = await server.wait_for_submission(
            job_id=final.job_id,
            connection_id=connection_id,
            after_sequence=after,
            timeout=timeout,
        )
        self._assert_submission_ntime(submission.ntime, final.ntime)
        self.logger.info("Latest clean job survived a %d-job burst", burst_jobs)

    @validation_test(1849)
    def test_90_fragmented_consecutive_and_boundary_messages(self) -> None:
        async def run() -> None:
            type(self)._handshake = (
                await self._case_90_fragmented_consecutive_and_boundary_messages(
                    type(self)._server,
                    type(self)._handshake,
                    type(self)._settings,
                )
            )

        self._run_ordered_case(run())

    @validation_test(1849)
    def test_91_invalid_messages_do_not_create_work_or_corrupt_state(self) -> None:
        self._run_ordered_case(
            self._case_91_invalid_messages_do_not_create_work_or_corrupt_state(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
            )
        )

    @validation_test(1897)
    def test_92_version_rolling_requires_accepted_configure(self) -> None:
        async def run() -> None:
            type(self)._handshake = (
                await self._case_92_version_rolling_requires_accepted_configure(
                    type(self)._server,
                    type(self)._handshake,
                    type(self)._settings,
                )
            )

        self._run_ordered_case(run())

    @validation_test(1897)
    def test_93_zero_length_extranonce2_produces_work(self) -> None:
        self._run_ordered_case(
            self._case_93_zero_length_extranonce2_produces_work(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
            )
        )

    @validation_test(1897)
    def test_94_healthy_client_reconnects_reset_retry_history(self) -> None:
        async def run() -> None:
            type(self)._handshake = (
                await self._case_94_healthy_client_reconnects_reset_retry_history(
                    type(self)._server,
                    type(self)._handshake,
                    type(self)._settings,
                )
            )

        self._run_ordered_case(run())

    @validation_test(1897)
    def test_95_oversized_jobs_are_rejected_without_state_change(self) -> None:
        self._run_ordered_case(
            self._case_95_oversized_jobs_are_rejected_without_state_change(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
            )
        )

    @validation_test(1897)
    def test_96_burst_keeps_latest_clean_job_valid(self) -> None:
        self._run_ordered_case(
            self._case_96_burst_keeps_latest_clean_job_valid(
                type(self)._server,
                type(self)._handshake,
                type(self)._settings,
            )
        )
