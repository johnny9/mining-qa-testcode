from __future__ import annotations

import asyncio
import json
import tempfile
import unittest
from pathlib import Path

from miner_testcode.interfaces.fake_stratum import (
    STRATUM_V1_MAX_JSON_LINE_SIZE,
    FakeStratumV1Server,
    MiningJob,
)


class MiningJobTest(unittest.TestCase):
    def test_fixed_extranonce_preserves_the_solved_coinbase(self):
        seed = MiningJob.standard("seed")
        extra1, extra2 = "01020304050607", "1122334455667788"
        fixed = seed.with_fixed_extranonce2(extra2)
        before = bytes.fromhex(seed.coinbase_1 + extra1 + extra2 + seed.coinbase_2)
        after = bytes.fromhex(fixed.coinbase_1 + extra1 + fixed.coinbase_2)
        self.assertEqual(before, after)
        self.assertEqual(seed.version, fixed.version)
        self.assertEqual(seed.ntime, fixed.ntime)
        for invalid in ("0", "zz", "00 " * 2, "00" * 33):
            with self.assertRaises(ValueError):
                seed.with_fixed_extranonce2(invalid)

    def test_fixture_coinbase_is_complete_for_zero_and_normal_extranonces(self):
        for extra2_size in (0, 8, 32):
            job = MiningJob.standard("fixture", extranonce2_size=extra2_size)
            tx = bytes.fromhex(job.coinbase_1) + bytes(7 + extra2_size) + bytes.fromhex(job.coinbase_2)
            self.assertEqual(tx[4], 1)
            self.assertEqual(tx[5:37], bytes(32))
            self.assertEqual(tx[37:41], b"\xff" * 4)
            offset = 42 + tx[41] + 4
            self.assertEqual(tx[offset], 3)
            offset += 1
            for _ in range(3):
                offset += 8
                script_size = tx[offset]
                self.assertLess(script_size, 0xfd)
                offset += 1 + script_size
            self.assertEqual(len(tx) - offset, 4)

    def test_fixture_rejects_invalid_extranonce_sizes(self):
        for size in (-1, 33, 1.5, True):
            with self.assertRaises(ValueError):
                MiningJob.standard("bad", extranonce2_size=size)
        with self.assertRaises(ValueError):
            MiningJob.standard("too-large", extranonce1_size=32, extranonce2_size=32)

    def test_standard_job_is_valid_shape_and_copyable(self) -> None:
        job = MiningJob.standard("job-1")
        changed = job.with_changes(job_id="job-2", merkle_branches=("00" * 32,))

        self.assertEqual(job.notification()["params"][0], "job-1")
        self.assertEqual(changed.notification()["params"][0], "job-2")
        self.assertEqual(len(changed.notification()["params"][4]), 1)
        self.assertRegex(job.ntime, r"^[0-9a-f]{8}$")

    def test_job_id_matches_esp_miner_bound(self) -> None:
        self.assertEqual(MiningJob.standard("j" * 31).job_id, "j" * 31)
        for invalid in ("", "j" * 32):
            with self.subTest(invalid=invalid), self.assertRaisesRegex(
                ValueError, "job_id"
            ):
                MiningJob.standard(invalid)

    def test_server_rejects_unsafe_setup_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "extranonce2_size"):
            FakeStratumV1Server(extranonce2_size=33)
        with self.assertRaisesRegex(ValueError, "extranonce1"):
            FakeStratumV1Server(extranonce1="0")
        with self.assertRaisesRegex(ValueError, "version_mask"):
            FakeStratumV1Server(version_mask="ff")
        with self.assertRaisesRegex(ValueError, "configure_response"):
            FakeStratumV1Server(configure_response="accept")  # type: ignore[arg-type]


class FakeStratumV1ServerTest(unittest.IsolatedAsyncioTestCase):
    async def test_regression_selects_responsive_post_reboot_handshake(self):
        from tests.e2e.test_stratum_v1_regression import StratumV1RegressionTest
        requests = [
            {"id": 1, "method": "mining.configure", "params": [["version-rolling"], {}]},
            {"id": 2, "method": "mining.subscribe", "params": ["test-miner"]},
            {"id": 3, "method": "mining.authorize", "params": ["worker", "password"]},
        ]
        await self._send_requests(*requests)
        old = await self.server.wait_for_handshake(require_configure=True)
        reader, writer = await asyncio.open_connection("127.0.0.1", self.server.port)
        writer.write(b"".join(json.dumps(r).encode() + b"\n" for r in requests))
        await writer.drain()
        new = await self.server.wait_for_handshake(after_connection_id=old.connection_id,
                                                    require_configure=True)

        async def respond():
            while line := await reader.readline():
                request = json.loads(line)
                if request.get("method") == "mining.ping":
                    writer.write(json.dumps({"id": request["id"], "method": "pong", "params": []}).encode() + b"\n")
                    await writer.drain()

        responder = asyncio.create_task(respond())
        try:
            case = StratumV1RegressionTest("test_01_configure_extension_negotiation")
            actual = await case._wait_for_handshake(self.server, {"handshake_timeout": 1}, "worker")
            self.assertEqual(actual.connection_id, new.connection_id)
        finally:
            writer.close()
            await writer.wait_closed()
            responder.cancel()
            await asyncio.gather(responder, return_exceptions=True)

    async def test_regression_cannot_accept_an_unresponsive_handshake(self):
        from tests.e2e.test_stratum_v1_regression import StratumV1RegressionTest
        await self._send_requests(
            {"id": 1, "method": "mining.configure", "params": [["version-rolling"], {}]},
            {"id": 2, "method": "mining.subscribe", "params": ["test-miner"]},
            {"id": 3, "method": "mining.authorize", "params": ["worker", "password"]},
        )
        await self.server.wait_for_handshake(require_configure=True)
        case = StratumV1RegressionTest("test_01_configure_extension_negotiation")
        with self.assertRaises(TimeoutError):
            await case._wait_for_handshake(self.server, {"handshake_timeout": .05}, "worker")

    async def asyncSetUp(self) -> None:
        self.server = FakeStratumV1Server()
        await self.server.start()
        self.reader, self.writer = await asyncio.open_connection(
            "127.0.0.1", self.server.port
        )

    async def asyncTearDown(self) -> None:
        self.writer.close()
        await asyncio.gather(self.writer.wait_closed(), return_exceptions=True)
        await self.server.close()

    async def _send_requests(self, *requests: object) -> None:
        self.writer.write(
            b"".join(
                json.dumps(request, separators=(",", ":")).encode() + b"\n"
                for request in requests
            )
        )
        await self.writer.drain()

    async def _read_json(self) -> object:
        line = await asyncio.wait_for(self.reader.readline(), timeout=1)
        self.assertTrue(line)
        return json.loads(line)

    async def test_auto_handshake_accepts_configure_subscribe_and_authorize(self) -> None:
        await self._send_requests(
            {
                "id": 1,
                "method": "mining.configure",
                "params": [["version-rolling"], {}],
            },
            {"id": 2, "method": "mining.subscribe", "params": ["bitaxe/test"]},
            {
                "id": 3,
                "method": "mining.authorize",
                "params": ["regression.worker", "private-password"],
            },
        )

        configure = await self._read_json()
        subscribe = await self._read_json()
        authorize = await self._read_json()
        handshake = await self.server.wait_for_handshake(require_configure=True)

        self.assertEqual(configure["id"], 1)
        self.assertTrue(configure["result"]["version-rolling"])
        self.assertEqual(subscribe["id"], 2)
        self.assertEqual(subscribe["result"][1], "01020304050607")
        self.assertEqual(subscribe["result"][2], 8)
        self.assertEqual(authorize, {"id": 3, "result": True, "error": None})
        self.assertEqual(handshake.subscribe.params, ["bitaxe/test"])
        self.assertEqual(handshake.authorize.params[0], "regression.worker")
        self.assertEqual(handshake.authorize.params[1], "<redacted>")
        self.assertNotIn(b"private-password", handshake.authorize.raw)

        with tempfile.TemporaryDirectory() as directory:
            transcript = Path(directory) / "stratum.jsonl"
            self.server.write_transcript(transcript)
            evidence = transcript.read_text(encoding="utf-8")
        self.assertNotIn("private-password", evidence)
        self.assertIn("<redacted>", evidence)

    async def test_configure_response_can_be_deferred_and_rejected(self) -> None:
        self.server.configure_response = None
        await self._send_requests(
            {
                "id": 41,
                "method": "mining.configure",
                "params": [["version-rolling"], {}],
            }
        )
        request = await self.server.wait_for_request("mining.configure")
        with self.assertRaises(TimeoutError):
            await asyncio.wait_for(self.reader.readline(), timeout=0.02)

        await self.server.send_configure_response(
            request.message_id,
            accepted=False,
            session=request.connection_id,
        )
        rejected = await self._read_json()
        self.assertEqual(
            rejected,
            {"id": 41, "result": {"version-rolling": False}, "error": None},
        )

        self.server.configure_response = True
        await self._send_requests(
            {
                "id": 42,
                "method": "mining.configure",
                "params": [["version-rolling"], {}],
            }
        )
        accepted = await self._read_json()
        self.assertEqual(accepted["id"], 42)
        self.assertTrue(accepted["result"]["version-rolling"])
        self.assertEqual(
            accepted["result"]["version-rolling.mask"], self.server.version_mask
        )

    async def test_scripted_fragmented_job_records_and_accepts_share(self) -> None:
        await self._send_requests(
            {"id": 2, "method": "mining.subscribe", "params": ["client"]},
            {
                "id": 3,
                "method": "mining.authorize",
                "params": ["regression.worker", "x"],
            },
        )
        await self._read_json()
        await self._read_json()
        handshake = await self.server.wait_for_handshake()

        job = MiningJob.standard("fragmented-job")
        await self.server.send_job(
            job,
            difficulty=64,
            session=handshake.connection_id,
            fragment_sizes=[1, 2, 3, 5, 8, 13],
        )
        difficulty = await self._read_json()
        notify = await self._read_json()
        self.assertEqual(difficulty["method"], "mining.set_difficulty")
        self.assertEqual(notify, job.notification())

        await self._send_requests(
            {
                "id": 4,
                "method": "mining.submit",
                "params": [
                    "regression.worker",
                    job.job_id,
                    "0000000000000000",
                    job.ntime,
                    "12345678",
                    "00000000",
                ],
            }
        )
        submission = await self.server.wait_for_submission(job_id=job.job_id)
        response = await self._read_json()

        self.assertEqual(submission.username, "regression.worker")
        self.assertEqual(submission.extranonce2, "0000000000000000")
        self.assertEqual(submission.version_bits, "00000000")
        self.assertEqual(response, {"id": 4, "result": True, "error": None})

    async def test_raw_interface_preserves_exact_boundary_and_successor(self) -> None:
        session = await self.server.wait_for_connection()
        maximum_line = b"{}" + b" " * (STRATUM_V1_MAX_JSON_LINE_SIZE - 2)
        successor = {"id": None, "method": "mining.set_difficulty", "params": [1]}
        successor_line = json.dumps(successor, separators=(",", ":")).encode()
        await self.server.send_raw(
            maximum_line + b"\n" + successor_line + b"\n",
            session=session,
            fragment_sizes=[997, 4096, 8192],
            label="exact-boundary-and-successor",
        )

        first = await asyncio.wait_for(self.reader.readline(), timeout=1)
        second = await asyncio.wait_for(self.reader.readline(), timeout=1)
        self.assertEqual(len(first) - 1, STRATUM_V1_MAX_JSON_LINE_SIZE)
        self.assertEqual(json.loads(first), {})
        self.assertEqual(json.loads(second), successor)

    async def test_waits_for_reconnection_after_transport_failure(self) -> None:
        first = await self.server.wait_for_connection()
        self.writer.close()
        await self.writer.wait_closed()
        self.reader, self.writer = await asyncio.open_connection(
            "127.0.0.1", self.server.port
        )
        second = await self.server.wait_for_connection(
            after_connection_id=first.connection_id
        )
        self.assertGreater(second.connection_id, first.connection_id)

    async def test_close_does_not_wait_for_a_connected_client(self) -> None:
        await asyncio.wait_for(self.server.close(), timeout=2.0)

    async def test_no_submission_assertion_filters_other_jobs(self) -> None:
        await self._send_requests(
            {
                "id": 5,
                "method": "mining.submit",
                "params": ["worker", "old-job", "00", "00000000", "00000000"],
            }
        )
        await self.server.wait_for_submission(job_id="old-job")
        await self._read_json()
        await self.server.assert_no_submission(job_id="rejected-job", duration=0.02)

    async def test_submission_policy_can_reject_a_well_formed_share(self) -> None:
        self.server.submission_policy = lambda submission: submission.job_id != "reject-me"
        await self._send_requests(
            {
                "id": 8,
                "method": "mining.submit",
                "params": ["worker", "reject-me", "00", "00000000", "00000000"],
            }
        )
        submission = await self.server.wait_for_submission(job_id="reject-me")
        response = await self._read_json()
        self.assertEqual(submission.request_id, 8)
        self.assertFalse(response["result"])
        self.assertEqual(response["error"][0], 23)


if __name__ == "__main__":
    unittest.main()
