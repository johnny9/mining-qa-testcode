from __future__ import annotations

import json
import unittest
from pathlib import Path

from miner_testcode.errors import ConfigError
from miner_testcode.orchestration import (
    load_orchestration_metadata,
    verify_orchestrated_testcode,
)
from miner_testcode.provenance import ResolvedTestCode
from miner_testcode.results import TestCodeRecord


def metadata() -> dict[str, object]:
    return {
        "contract_version": 2,
        "project_id": "firmware",
        "gate_id": "firmware-advisory",
        "gate_revision_id": "gate-rev-0001",
        "suite_id": "mock-device-smoke",
        "suite_revision_id": "suite-rev-0001",
        "trigger_id": "manual-local",
        "trigger_revision_id": "trigger-rev-0001",
        "trigger_type": "manual",
        "definition_digest": "a" * 64,
        "central_gate_run_id": "global-run-0001",
        "lab_id": "lab-east",
        "public_lab_label": "East Lab",
        "platform_class": "gamma-600",
        "device_model": "Gamma 602",
        "lab_execution_id": "execution-east-0001",
        "local_gate_run_id": "local-run-east-0001",
        "assignment_id": "assignment-east-0001",
        "attempt_id": "attempt-east-0001",
        "attempt": 1,
        "source": {
            "repository": "owner/firmware",
            "commit_sha": "0" * 40,
            "ref_name": "main",
            "pr_number": None,
        },
        "testcode": {
            "repository": "johnny9/mining-qa-testcode",
            "ref": "main",
            "commit_sha": "1" * 40,
        },
    }


def environment(value: dict[str, object]) -> dict[str, str]:
    return {
        "MINER_TEST_ORCHESTRATION_METADATA": json.dumps(value),
        "MINER_TEST_EXTERNAL_RUN_ID": str(value["assignment_id"]),
        "GITHUB_REPOSITORY": "owner/firmware",
        "GITHUB_SHA": "0" * 40,
        "GITHUB_REF_NAME": "main",
    }


class OrchestrationV2Test(unittest.TestCase):
    def test_validates_and_separates_public_and_private_correlation(self) -> None:
        value = metadata()
        parsed = load_orchestration_metadata(environment(value))

        self.assertIsNotNone(parsed)
        assert parsed is not None
        pointer = parsed.private_correlation()
        public = parsed.public_section("runner-0001")
        self.assertEqual(pointer["local_gate_run_id"], "local-run-east-0001")
        self.assertNotIn("local_gate_run_id", public)
        self.assertEqual(public["run_id"], "runner-0001")
        self.assertEqual(public["source"], value["source"])

    def test_rejects_unknown_fields_and_environment_mismatch(self) -> None:
        value = metadata()
        value["device_path"] = "/private/device"
        with self.assertRaisesRegex(ConfigError, "unknown device_path"):
            load_orchestration_metadata(environment(value))

        value = metadata()
        mismatched = environment(value)
        mismatched["MINER_TEST_EXTERNAL_RUN_ID"] = "other-assignment"
        with self.assertRaisesRegex(ConfigError, "MINER_TEST_EXTERNAL_RUN_ID"):
            load_orchestration_metadata(mismatched)

    def test_rejects_dirty_v2_unless_local_development_is_explicit(self) -> None:
        value = metadata()
        parsed = load_orchestration_metadata(environment(value))
        assert parsed is not None
        testcode = ResolvedTestCode(
            root=Path("."),
            record=TestCodeRecord(
                repository="johnny9/mining-qa-testcode",
                commit_sha="1" * 40,
                url="https://github.com/johnny9/mining-qa-testcode",
                dirty=True,
            ),
        )
        with self.assertRaisesRegex(ConfigError, "clean testcode worktree"):
            verify_orchestrated_testcode(parsed, testcode, {})
        verify_orchestrated_testcode(
            parsed, testcode, {"MINING_QA_INTEGRATION_DEVELOPMENT": "1"}
        )
