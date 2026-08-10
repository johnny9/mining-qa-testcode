from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from miner_testcode.artifacts import RunArtifacts
from miner_testcode.config import ConfigError
from miner_testcode.provenance import ResolvedTestCode
from miner_testcode.results import PublisherRecord, RunSummary, TestCodeRecord
from miner_testcode.runner import (
    MiningTestResult,
    _result_pointer_payload,
    _write_artifact_manifest,
    _write_result_pointer,
)
from miner_testcode.telemetry import STANDARD_MINING_METRICS, TelemetryCapture


class ResultMarkerTest(unittest.TestCase):
    def test_writes_versioned_result_pointer_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = RunSummary(
                run_id="run-1",
                artifact_root=root / "artifacts",
                started_at=1.0,
                finished_at=2.0,
                devices=(),
                tests=(),
                tests_run=1,
                failures=0,
                errors=0,
                skipped=0,
                expected_failures=0,
                unexpected_successes=0,
                successful=True,
                publishers=[
                    PublisherRecord(
                        name="mining_qa_status",
                        success=True,
                        required=True,
                        url="https://status.example/results/child-1",
                    )
                ],
            )
            pointer = root / "jobs" / "result-pointer.json"

            payload = _result_pointer_payload(summary, successful=True)
            _write_result_pointer(pointer, payload)

            self.assertEqual(json.loads(pointer.read_text())["contract_version"], 1)
            self.assertEqual(json.loads(pointer.read_text())["status"], "passed")
            self.assertEqual(list(pointer.parent.glob("*.tmp")), [])

            with self.assertRaisesRegex(ConfigError, "exceeds 64 KiB"):
                _write_result_pointer(pointer, {"detail": "x" * (65 * 1024)})

    def test_writes_bounded_hash_verified_artifact_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            root.mkdir()
            case = root / "001-case"
            case.mkdir()
            (root / "runner.log").write_text("runner output\n", encoding="utf-8")
            (case / "test.log").write_text("test output\n", encoding="utf-8")
            summary = RunSummary(
                run_id="run-1",
                artifact_root=root,
                started_at=1.0,
                finished_at=2.0,
                devices=(),
                tests=(),
                tests_run=0,
                failures=0,
                errors=0,
                skipped=0,
                expected_failures=0,
                unexpected_successes=0,
                successful=True,
            )

            descriptor = _write_artifact_manifest(summary)
            manifest = json.loads(
                (root / "orchestration-artifacts.json").read_text(encoding="utf-8")
            )
            payload = _result_pointer_payload(
                summary,
                successful=True,
                artifact_manifest=descriptor,
            )

        self.assertEqual(manifest["version"], 1)
        self.assertEqual(
            {item["path"] for item in manifest["artifacts"]},
            {"001-case/test.log", "runner.log"},
        )
        self.assertTrue(
            all(len(item["sha256"]) == 64 for item in manifest["artifacts"])
        )
        self.assertEqual(payload["artifact_manifest"], descriptor)

    def test_artifact_manifest_rejects_symlinks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "artifacts"
            root.mkdir()
            target = root / "target.log"
            target.write_text("output\n", encoding="utf-8")
            (root / "linked.log").symlink_to(target)
            summary = RunSummary(
                run_id="run-1",
                artifact_root=root,
                started_at=1.0,
                finished_at=2.0,
                devices=(),
                tests=(),
                tests_run=0,
                failures=0,
                errors=0,
                skipped=0,
                expected_failures=0,
                unexpected_successes=0,
                successful=True,
            )

            with self.assertRaisesRegex(ConfigError, "symlinks"):
                _write_artifact_manifest(summary)

    def test_success_marker_names_the_test_method(self) -> None:
        class ExampleCase(unittest.TestCase):
            def test_named_feature(self) -> None:
                pass

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            artifacts = RunArtifacts(root, "run")
            capture = TelemetryCapture(
                STANDARD_MINING_METRICS,
                event_path=artifacts.path / "telemetry.jsonl",
                started_at=100.0,
            )
            test = ExampleCase("test_named_feature")
            test._context = SimpleNamespace(  # type: ignore[attr-defined]
                device_config=SimpleNamespace(publication_name="Gamma")
            )
            test.device = SimpleNamespace(telemetry=capture)  # type: ignore[attr-defined]
            result = MiningTestResult(
                io.StringIO(),
                True,
                0,
                artifacts=artifacts,
                test_code=ResolvedTestCode(
                    root=Path(__file__).resolve().parents[2],
                    record=TestCodeRecord(
                        repository="owner/mining-qa-testcode",
                        commit_sha="a" * 40,
                        url="https://github.com/owner/mining-qa-testcode",
                    ),
                ),
            )

            result.startTest(test)
            result.addSuccess(test)
            markers = capture.to_dict()["markers"]

        self.assertEqual(len(markers), 1)
        self.assertEqual(markers[0]["label"], "test_named_feature passed")
        self.assertEqual(markers[0]["status"], "good")


if __name__ == "__main__":
    unittest.main()
