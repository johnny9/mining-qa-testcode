from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping

from .errors import ConfigError
from .provenance import ResolvedTestCode


MAX_METADATA_BYTES = 64 * 1024
_OPAQUE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_SHA = re.compile(r"^[0-9a-f]{40}$")
_DIGEST = re.compile(r"^[0-9a-f]{64}$")

_V2_KEYS = frozenset(
    {
        "contract_version",
        "project_id",
        "gate_id",
        "gate_revision_id",
        "suite_id",
        "suite_revision_id",
        "trigger_id",
        "trigger_revision_id",
        "trigger_type",
        "definition_digest",
        "central_gate_run_id",
        "lab_id",
        "public_lab_label",
        "platform_class",
        "device_model",
        "lab_execution_id",
        "local_gate_run_id",
        "assignment_id",
        "attempt_id",
        "attempt",
        "source",
        "testcode",
    }
)
_SOURCE_KEYS = frozenset({"repository", "commit_sha", "ref_name", "pr_number"})
_TESTCODE_KEYS = frozenset({"repository", "ref", "commit_sha"})


def _strict_keys(value: Mapping[str, Any], expected: frozenset[str], context: str) -> None:
    actual = frozenset(value)
    if actual == expected:
        return
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    detail = []
    if missing:
        detail.append(f"missing {', '.join(missing)}")
    if unknown:
        detail.append(f"unknown {', '.join(unknown)}")
    raise ConfigError(f"{context} has invalid fields: {'; '.join(detail)}")


def _string(value: Any, context: str, *, maximum: int = 128) -> str:
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ConfigError(f"{context} must be a non-empty string up to {maximum} characters")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ConfigError(f"{context} must not contain control characters")
    return value


def _opaque(value: Any, context: str) -> str:
    parsed = _string(value, context)
    if not _OPAQUE_ID.fullmatch(parsed):
        raise ConfigError(f"{context} must be an opaque identifier")
    return parsed


def _repository(value: Any, context: str) -> str:
    parsed = _string(value, context, maximum=200)
    if not _REPOSITORY.fullmatch(parsed):
        raise ConfigError(f"{context} must have owner/name form")
    return parsed


def _sha(value: Any, context: str) -> str:
    if not isinstance(value, str) or not _SHA.fullmatch(value):
        raise ConfigError(f"{context} must be a 40-character lowercase commit SHA")
    return value


@dataclass(frozen=True, slots=True)
class OrchestrationMetadata:
    contract_version: int
    raw: Mapping[str, Any]

    @property
    def is_v2(self) -> bool:
        return self.contract_version == 2

    def private_correlation(self) -> dict[str, str]:
        if not self.is_v2:
            return {}
        return {
            "central_gate_run_id": str(self.raw["central_gate_run_id"]),
            "lab_id": str(self.raw["lab_id"]),
            "lab_execution_id": str(self.raw["lab_execution_id"]),
            "local_gate_run_id": str(self.raw["local_gate_run_id"]),
            "assignment_id": str(self.raw["assignment_id"]),
            "attempt_id": str(self.raw["attempt_id"]),
            "definition_digest": str(self.raw["definition_digest"]),
        }

    def public_section(self, run_id: str) -> dict[str, Any]:
        if not self.is_v2:
            return dict(self.raw)
        public_keys = (
            "project_id",
            "gate_id",
            "gate_revision_id",
            "suite_id",
            "suite_revision_id",
            "trigger_id",
            "trigger_revision_id",
            "trigger_type",
            "definition_digest",
            "central_gate_run_id",
            "lab_id",
            "public_lab_label",
            "platform_class",
            "device_model",
            "lab_execution_id",
            "assignment_id",
            "attempt_id",
        )
        return {
            "contract_version": 2,
            **{key: self.raw[key] for key in public_keys},
            "run_id": run_id,
            "source": dict(self.raw["source"]),
            "testcode": dict(self.raw["testcode"]),
        }


def _validate_v2(value: dict[str, Any], environ: Mapping[str, str]) -> None:
    _strict_keys(value, _V2_KEYS, "orchestration v2 metadata")
    for key in (
        "project_id",
        "gate_id",
        "gate_revision_id",
        "suite_id",
        "suite_revision_id",
        "trigger_id",
        "trigger_revision_id",
        "central_gate_run_id",
        "lab_id",
        "lab_execution_id",
        "local_gate_run_id",
        "assignment_id",
        "attempt_id",
    ):
        _opaque(value[key], f"orchestration.{key}")
    _string(value["public_lab_label"], "orchestration.public_lab_label", maximum=80)
    _string(value["platform_class"], "orchestration.platform_class", maximum=80)
    _string(value["device_model"], "orchestration.device_model", maximum=80)
    if value["trigger_type"] != "manual":
        raise ConfigError("orchestration.trigger_type must be manual in contract v2")
    if not isinstance(value["definition_digest"], str) or not _DIGEST.fullmatch(
        value["definition_digest"]
    ):
        raise ConfigError("orchestration.definition_digest must be a lowercase SHA-256")
    attempt = value["attempt"]
    if isinstance(attempt, bool) or not isinstance(attempt, int) or not 1 <= attempt <= 1000:
        raise ConfigError("orchestration.attempt must be an integer from 1 through 1000")

    source = value["source"]
    if not isinstance(source, dict):
        raise ConfigError("orchestration.source must be an object")
    _strict_keys(source, _SOURCE_KEYS, "orchestration.source")
    _repository(source["repository"], "orchestration.source.repository")
    _sha(source["commit_sha"], "orchestration.source.commit_sha")
    _string(source["ref_name"], "orchestration.source.ref_name", maximum=255)
    pr_number = source["pr_number"]
    if pr_number is not None and (
        isinstance(pr_number, bool)
        or not isinstance(pr_number, int)
        or not 1 <= pr_number <= 2_147_483_647
    ):
        raise ConfigError("orchestration.source.pr_number must be null or a positive integer")

    testcode = value["testcode"]
    if not isinstance(testcode, dict):
        raise ConfigError("orchestration.testcode must be an object")
    _strict_keys(testcode, _TESTCODE_KEYS, "orchestration.testcode")
    _repository(testcode["repository"], "orchestration.testcode.repository")
    _string(testcode["ref"], "orchestration.testcode.ref", maximum=255)
    _sha(testcode["commit_sha"], "orchestration.testcode.commit_sha")

    expected_environment = {
        "MINER_TEST_EXTERNAL_RUN_ID": value["assignment_id"],
        "GITHUB_REPOSITORY": source["repository"],
        "GITHUB_SHA": source["commit_sha"],
        "GITHUB_REF_NAME": source["ref_name"],
    }
    for name, expected in expected_environment.items():
        if environ.get(name) != expected:
            raise ConfigError(f"{name} does not match orchestration v2 metadata")
    if pr_number is None:
        if environ.get("MINER_TEST_PR_NUMBER", "").strip():
            raise ConfigError("MINER_TEST_PR_NUMBER must be absent for a non-PR source")
    elif environ.get("MINER_TEST_PR_NUMBER") != str(pr_number):
        raise ConfigError("MINER_TEST_PR_NUMBER does not match orchestration v2 metadata")


def load_orchestration_metadata(
    environ: Mapping[str, str] | None = None,
) -> OrchestrationMetadata | None:
    actual_environment = os.environ if environ is None else environ
    raw = actual_environment.get("MINER_TEST_ORCHESTRATION_METADATA", "").strip()
    if not raw:
        return None
    if len(raw.encode("utf-8")) > MAX_METADATA_BYTES:
        raise ConfigError("orchestration metadata exceeds 64 KiB")
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ConfigError("MINER_TEST_ORCHESTRATION_METADATA must be JSON") from exc
    if not isinstance(value, dict):
        raise ConfigError("MINER_TEST_ORCHESTRATION_METADATA must be a JSON object")
    version = value.get("contract_version", 1)
    if isinstance(version, bool) or not isinstance(version, int) or version not in {1, 2}:
        raise ConfigError(f"unsupported orchestration contract version: {version!r}")
    if version == 2:
        _validate_v2(value, actual_environment)
    return OrchestrationMetadata(version, MappingProxyType(value))


def verify_orchestrated_testcode(
    metadata: OrchestrationMetadata | None,
    test_code: ResolvedTestCode,
    environ: Mapping[str, str] | None = None,
) -> None:
    if metadata is None or "testcode" not in metadata.raw:
        return
    expected = metadata.raw["testcode"]
    if not isinstance(expected, Mapping):
        raise ConfigError("orchestration testcode metadata must be an object")
    if expected.get("repository") != test_code.record.repository:
        raise ConfigError("installed testcode repository does not match orchestration metadata")
    if str(expected.get("commit_sha", "")).lower() != test_code.record.commit_sha.lower():
        raise ConfigError("installed testcode commit does not match orchestration metadata")
    actual_environment = os.environ if environ is None else environ
    if (
        metadata.is_v2
        and test_code.record.dirty
        and actual_environment.get("MINING_QA_INTEGRATION_DEVELOPMENT") != "1"
    ):
        raise ConfigError("orchestration v2 requires a clean testcode worktree")
