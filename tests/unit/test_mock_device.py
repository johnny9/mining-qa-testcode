from __future__ import annotations

import asyncio
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from miner_testcode.interfaces.fake_stratum import FakeStratumV1Server, MiningJob
from miner_testcode.mock_device import (
    MockServer,
    MockState,
    _validate_bind_host,
    _validated_path,
)


class MockDeviceContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.state = MockState(root / "state.json", root / "events.jsonl")
        self.state.reset("pass", [])
        self.server = MockServer(("127.0.0.1", 0), self.state)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)
        self.temporary.cleanup()

    def request(self, method: str, path: str, body: dict | None = None) -> tuple[int, dict]:
        encoded = json.dumps(body).encode() if body is not None else None
        request = Request(
            self.base_url + path,
            data=encoded,
            method=method,
            headers={"content-type": "application/json"} if encoded else {},
        )
        try:
            with urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read())
            finally:
                exc.close()

    def request_text(self, method: str, path: str) -> tuple[int, str]:
        request = Request(self.base_url + path, method=method)
        with urlopen(request, timeout=2) as response:
            return response.status, response.read().decode("utf-8")

    def test_scenario_lock_fault_counts_and_active_state(self) -> None:
        status, body = self.request(
            "PUT",
            "/__mock/v1/scenario",
            {"contract_version": 1, "scenario": "identity-mismatch", "transition_delay_ms": 1},
        )
        self.assertEqual((status, body["scenario"]), (200, "identity-mismatch"))
        status, info = self.request("GET", "/api/system/info")
        self.assertEqual((status, info["boardVersion"]), (200, "601"))
        self.assertFalse(any(item["kind"] == "settings_patch" for item in self.state.events))
        status, body = self.request(
            "PUT",
            "/__mock/v1/scenario",
            {"contract_version": 1, "scenario": "pass", "transition_delay_ms": 1},
        )
        self.assertEqual((status, body["error"]["code"]), (409, "scenario_active"))

        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "pass", "privacy_canaries": []},
        )
        status, _ = self.request(
            "PUT",
            "/__mock/v1/faults",
            {"contract_version": 1, "faults": [{"kind": "http_status", "count": 1, "status": 503}]},
        )
        self.assertEqual(status, 200)
        self.assertEqual(self.request("GET", "/api/system/info")[0], 503)
        self.assertEqual(self.request("GET", "/api/system/info")[0], 200)
        self.assertEqual(self.request("GET", "/__mock/v1/state")[1]["active_faults"], [])

    def test_unsupported_operations_are_forbidden_and_recorded(self) -> None:
        status, body = self.request("POST", "/api/system/ota", {})
        self.assertEqual((status, body["error"]["code"]), (409, "unsupported_operation"))
        status, body = self.request("DELETE", "/api/system")
        self.assertEqual((status, body["error"]["code"]), (409, "unsupported_operation"))
        self.assertEqual(
            [item["kind"] for item in self.state.events].count("unsupported_operation"),
            2,
        )

    def test_refuses_nonloopback_and_symlinked_control_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "loopback"):
            _validate_bind_host("0.0.0.0", 0)
        root = Path(self.temporary.name)
        target = root / "target"
        target.write_text("", encoding="utf-8")
        link = root / "link"
        link.symlink_to(target)
        with self.assertRaisesRegex(ValueError, "symlink"):
            _validated_path(str(link))
        directory_target = root / "directory-target"
        directory_target.mkdir()
        directory_link = root / "directory-link"
        directory_link.symlink_to(directory_target, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink"):
            _validated_path(str(directory_link / "state.json"))

    def test_required_http_and_cleanup_scenarios_are_deterministic(self) -> None:
        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "http-unavailable", "privacy_canaries": []},
        )
        self.assertEqual(self.request("GET", "/api/system/info")[0], 503)

        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "malformed-info", "privacy_canaries": []},
        )
        status, malformed = self.request("GET", "/api/system/info")
        self.assertEqual((status, malformed), (200, {"boardVersion": ["wrong-shape"]}))

        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "restart-never-returns", "privacy_canaries": []},
        )
        self.assertEqual(self.request("PATCH", "/api/system", {"stratumUser": "temporary.worker"})[0], 200)
        self.assertEqual(self.request("POST", "/api/system/restart", {})[0], 200)
        self.assertEqual(self.request("GET", "/api/system/info")[0], 503)

        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "cleanup-restore-rejected", "privacy_canaries": []},
        )
        self.assertEqual(self.request("PATCH", "/api/system", {"stratumUser": "temporary.worker"})[0], 200)
        status, rejected = self.request("PATCH", "/api/system", {"stratumUser": "integration.worker"})
        self.assertEqual((status, rejected["error"]["code"]), (409, "restore_rejected"))

        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "cleanup-restore-mismatch", "privacy_canaries": []},
        )
        self.request("PATCH", "/api/system", {"stratumUser": "temporary.worker"})
        self.request("POST", "/api/system/restart", {})
        self.request("PATCH", "/api/system", {"stratumUser": "integration.worker"})
        self.request("POST", "/api/system/restart", {})
        self.assertEqual(self.state.public_device()["stratumUser"], "restore-mismatch")

    def test_log_canaries_remain_in_private_mock_capture(self) -> None:
        canaries = ["device-canary-east", "pool-canary-east", "/private/canary/path"]
        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "log-privacy-canary", "privacy_canaries": canaries},
        )
        status, body = self.request_text("GET", "/api/system/logs")
        self.assertEqual(status, 200)
        for canary in canaries:
            self.assertIn(canary, body)

    def test_all_fault_shapes_are_bounded_and_reset_clears_them(self) -> None:
        faults = [
            {"kind": "http_status", "count": 1, "status": 503},
            {"kind": "drop_connection", "count": 1},
            {"kind": "delay_ms", "count": 1, "delay_ms": 1},
            {"kind": "malformed_json", "count": 1},
            {"kind": "reject_patch", "count": 1},
            {"kind": "ignore_patch", "count": 1},
            {"kind": "stay_offline_after_restart", "count": 1},
            {"kind": "stratum_disconnect_stage", "count": 1, "stage": "notify"},
        ]
        status, body = self.request(
            "PUT",
            "/__mock/v1/faults",
            {"contract_version": 1, "faults": faults},
        )
        self.assertEqual(status, 200)
        self.assertEqual({item["kind"] for item in body["active_faults"]}, {item["kind"] for item in faults})
        self.request(
            "POST",
            "/__mock/v1/reset",
            {"contract_version": 1, "baseline": "gamma-running", "scenario": "pass", "privacy_canaries": []},
        )
        self.assertEqual(self.request("GET", "/__mock/v1/state")[1]["active_faults"], [])
        status, _ = self.request(
            "PUT",
            "/__mock/v1/scenario",
            {"contract_version": 1, "scenario": "pass", "transition_delay_ms": True},
        )
        self.assertEqual(status, 400)
        status, _ = self.request(
            "PUT",
            "/__mock/v1/faults",
            {
                "contract_version": 1,
                "faults": [{"kind": "drop_connection", "count": 1, "unexpected": True}],
            },
        )
        self.assertEqual(status, 400)


class MockDeviceStratumScenarioTest(unittest.IsolatedAsyncioTestCase):
    async def run_stratum_scenario(self, scenario: str) -> tuple[MockState, FakeStratumV1Server]:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        state = MockState(root / "state.json", root / "events.jsonl")
        state.reset(scenario, [])
        server = FakeStratumV1Server(host="127.0.0.1", port=0)
        await server.start()
        self.addAsyncCleanup(server.close)
        self.addCleanup(state.stop_stratum)
        state.device["stratumPort"] = server.port
        state.start_stratum()
        handshake = await server.wait_for_handshake(timeout=2)
        await server.send_job(
            MiningJob.standard(f"{scenario}-job"),
            difficulty=1.0,
            session=handshake.connection_id,
        )
        return state, server

    async def test_test_failure_records_rejected_share(self) -> None:
        state, server = await self.run_stratum_scenario("test-failure")
        await server.wait_for_submission(timeout=2)
        async with asyncio.timeout(2):
            while int(state.device["sharesRejected"]) < 1:
                await asyncio.sleep(0.01)
        self.assertEqual(state.device["sharesAccepted"], 0)

    async def test_stratum_disconnect_never_submits(self) -> None:
        state, server = await self.run_stratum_scenario("stratum-disconnect")
        async with asyncio.timeout(2):
            while not any(
                event["kind"] == "fault_applied"
                and event["detail"].get("fault") == "stratum_disconnect_stage"
                for event in state.events
            ):
                await asyncio.sleep(0.01)
        self.assertEqual(server.submissions, ())


if __name__ == "__main__":
    unittest.main()
