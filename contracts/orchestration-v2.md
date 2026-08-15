# Mining QA orchestration contract v2

This document defines the version-2 process boundary between `mining-qa-lab`
and `mining-qa-testcode`. The coordinated copy in the other repository must
remain byte-for-byte identical. Neither repository imports the other as a
Python package.

Version 2 adds the distributed correlation chain and a strict public/private
split. Version 1 remains supported during the reader-first migration described
at the end of this document.

## Invocation

The Lab invokes the runner exactly as in version 1:

```text
miner-test --config PROFILE --pattern PATTERN
           [--device NAME ...]
           [--validation-pr NUMBER ...]
```

Exit status `0` means tests, cleanup, and required publishers completed
successfully. Nonzero means failed tests or a runner/configuration/
infrastructure error. A present valid result pointer is authoritative for the
more precise `passed`, `failed`, `error`, or `skipped` status.

The shell command is constructed only from the Lab's validated private binding
and fixed CLI vocabulary. No Status field is executed as a command or used as
a profile/device path.

## Environment supplied by the Lab

| Name | Contract |
|---|---|
| `MINER_TEST_ORCHESTRATION_METADATA` | Version-2 bounded JSON object below. |
| `MINER_TEST_EXTERNAL_RUN_ID` | Must exactly equal metadata `assignment_id`. |
| `MINER_TEST_RESULT_POINTER` | Absolute or worker-local path for atomic pointer replacement. |
| `GITHUB_REPOSITORY` | Must exactly equal metadata `source.repository`. |
| `GITHUB_SHA` | Must exactly equal metadata `source.commit_sha`. |
| `GITHUB_REF_NAME` | Must exactly equal metadata `source.ref_name`. |
| `MINER_TEST_PR_NUMBER` | Present only when metadata `source.pr_number` is not null and must equal it. |

The Lab passes only its configured allowlist plus these explicit values. SSH
execution disables agent forwarding. The metadata and pointer are each limited
to 64 KiB of UTF-8 JSON.

## Validation primitives

- Opaque IDs are 1–128 ASCII characters matching
  `[A-Za-z0-9][A-Za-z0-9._:-]{0,127}`. They are never parsed for hierarchy.
- `definition_digest` is exactly 64 lowercase hexadecimal characters.
- Repository names use `owner/name` and are at most 200 characters.
- Commit SHAs are exactly 40 lowercase hexadecimal characters in version 2.
- `ref_name` is 0–255 characters; a PR number is null or a positive integer no
  greater than 2147483647.
- Public human labels and platform/model classifications are 1–80 printable
  characters and must already be non-identifying.
- Unknown fields are rejected. Adding a field requires a coordinated
  reader-first contract update.
- Booleans are never accepted as integers. Duplicate JSON keys, invalid UTF-8,
  non-JSON numeric values, and values outside these bounds fail validation.

## Metadata JSON

Every field below is required; only `source.pr_number` may be null.

```json
{
  "contract_version": 2,
  "project_id": "firmware",
  "gate_id": "firmware-advisory",
  "gate_revision_id": "gate-rev-0001",
  "suite_id": "mock-device-smoke",
  "suite_revision_id": "suite-rev-0001",
  "trigger_id": "manual-local",
  "trigger_revision_id": "trigger-rev-0001",
  "trigger_type": "manual",
  "definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78",
  "central_gate_run_id": "global-run-0001",
  "lab_id": "lab-east",
  "public_lab_label": "East Lab",
  "platform_class": "gamma-600",
  "device_model": "Gamma 602",
  "lab_execution_id": "lab-execution-east-0001",
  "local_gate_run_id": "local-run-east-0001",
  "assignment_id": "assignment-east-0001",
  "attempt_id": "attempt-east-0001",
  "attempt": 1,
  "source": {
    "repository": "owner/firmware",
    "commit_sha": "0123456789abcdef0123456789abcdef01234567",
    "ref_name": "main",
    "pr_number": null
  },
  "testcode": {
    "repository": "johnny9/mining-qa-testcode",
    "ref": "main",
    "commit_sha": "89abcdef0123456789abcdef0123456789abcdef"
  }
}
```

`trigger_type` is `manual` in the proof of concept. `attempt` is 1–1000 and
must equal the immutable Lab attempt record associated with `attempt_id`.

The definition digest is supplied by Status and verified by Lab against its
frozen offer. It covers only the canonical portable definition in the
Status/Lab coordination contract. It does not cover private binding, profile,
device selection, local paths, or credentials.

Before allocating an artifact directory, constructing a device object, opening
a network/serial interface, or invoking any publisher, the runner validates:

1. the complete metadata object and cross-field environment equality;
2. its executing repository origin and exact HEAD against `testcode`;
3. its clean-worktree policy for an orchestrated exact-source run; and
4. the supported contract version.

Any mismatch returns a configuration/infrastructure failure and writes no
hardware-facing evidence. The runner treats IDs as immutable invocation data;
it never reads replacements from mutable global state.

## Correlation ownership

| Identity | Created by | Visibility | Meaning |
|---|---|---|---|
| `central_gate_run_id` | Status | public | One frozen global advisory run. |
| `lab_execution_id` | Status | public | One frozen participating lab execution. |
| `lab_id` | Status registration | public | Sanitized coordination identity, never a device. |
| `local_gate_run_id` | Lab | private | Durable local execution container. |
| `assignment_id` | Lab | public opaque correlation | One stable runner assignment. |
| `attempt_id` | Lab | public opaque correlation | One immutable assignment attempt. |
| `run_id` | Testcode | public opaque correlation | One runner invocation/result. |
| `definition_digest` | Status | public | Exact canonical portable input. |

No identity may be substituted for another. Public IDs are independently
generated random/opaque values and cannot encode or derive from a device ID,
serial number, USB/MAC/IP identity, hostname, pool user, payout address, local
path, setup, profile, or credential.

## Result pointer written by Testcode

The runner atomically replaces `MINER_TEST_RESULT_POINTER` with this object:

```json
{
  "contract_version": 2,
  "run_id": "runner-east-0001",
  "successful": true,
  "status": "passed",
  "correlation": {
    "central_gate_run_id": "global-run-0001",
    "lab_id": "lab-east",
    "lab_execution_id": "lab-execution-east-0001",
    "local_gate_run_id": "local-run-east-0001",
    "assignment_id": "assignment-east-0001",
    "attempt_id": "attempt-east-0001",
    "definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78"
  },
  "artifact_root": "/private/local/path",
  "artifact_manifest": {
    "path": "orchestration-artifacts.json",
    "size_bytes": 1234,
    "sha256": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  },
  "publishers": [
    {
      "name": "mining_qa_status",
      "success": true,
      "required": true,
      "result_id": "result-east-0001",
      "url": "http://localhost:3000/results/result-east-0001",
      "detail": null
    }
  ]
}
```

- `run_id` is a new opaque ID for this invocation.
- `successful` reflects tests, cleanup, and required publishers. It must agree
  with `status`: only `passed` or policy-permitted `skipped` can be successful.
- `status` is `passed`, `failed`, `error`, or `skipped`; unknown values fail
  closed as `error`.
- Every correlation field is required and must byte-for-byte equal validated
  input. The pointer is private because it includes `local_gate_run_id` and
  `artifact_root`.
- The v2 artifact manifest is required, even when its `artifacts` list is
  empty. It follows the version-1 manifest format and limits: 256 KiB, 512
  entries, 50 MiB per artifact, 512 MiB total, safe relative paths, no
  symlinks/traversal, exact size and lowercase SHA-256.
- `publishers` has at most 16 records. `name`, `success`, and `required` are
  required. `result_id`, `url`, and single-line `detail` are nullable; each
  string is bounded to 2048 characters, with `name` and `result_id` also
  satisfying the opaque-ID rule.
- A successful required `mining_qa_status` publisher must return both immutable
  `result_id` and an HTTP(S) `url` matching the configured Status public origin.
- Lab reads at most 64 KiB plus one byte, rejects partial/oversized data, and
  validates every field before using it.

The pointer is the only Lab/Testcode machine result boundary. Lab never parses
worker logs to infer success and never reconstructs a child result from the
private artifact archive.

## Published child orchestration section

When version-2 metadata is present, the detailed child result sent to Status
contains exactly this additional allowlisted section:

```json
{
  "orchestration": {
    "contract_version": 2,
    "project_id": "firmware",
    "gate_id": "firmware-advisory",
    "gate_revision_id": "gate-rev-0001",
    "suite_id": "mock-device-smoke",
    "suite_revision_id": "suite-rev-0001",
    "trigger_id": "manual-local",
    "trigger_revision_id": "trigger-rev-0001",
    "trigger_type": "manual",
    "definition_digest": "ac88bc9309a751d70131dc5dde3dc5f2519a49bafa4626e66206714b215f7b78",
    "central_gate_run_id": "global-run-0001",
    "lab_id": "lab-east",
    "public_lab_label": "East Lab",
    "platform_class": "gamma-600",
    "device_model": "Gamma 602",
    "lab_execution_id": "lab-execution-east-0001",
    "assignment_id": "assignment-east-0001",
    "attempt_id": "attempt-east-0001",
    "run_id": "runner-east-0001",
    "source": {},
    "testcode": {}
  }
}
```

The abbreviated `source` and `testcode` objects have the exact shapes from the
metadata. `local_gate_run_id`, `artifact_root`, profile/setup/device names,
coordinates, credentials, and raw logs are forbidden. The section is built
from an allowlist, not by serializing the private pointer and deleting fields.

Status verifies this section against its frozen gate run and lab execution
before accepting the child. It does not trust the child to create or change a
global run.

## Sanitized log publication

Raw runner, process, SSH, device, and orchestrator logs remain private. After
test cleanup and interface close, Testcode may create one distinct sanitized
log artifact. It must:

1. apply exact-value removal using the invocation's private identity/secret
   set and pattern scanning for paths, network/device/payout/pool identities;
2. contain no distinguishing fragment of a removed value;
3. pass a second independent scan over filename and complete bytes;
4. record sanitizer contract version, media type, byte size, and SHA-256; and
5. be uploaded only through the configured public child publisher.

If capture, sanitization, either scan, or upload fails, no log is published or
linked and the raw log is never used as fallback. Fixed typed placeholders are
allowed in sanitized log text but never in structured public identity fields.

## State and failure mapping

Lab assignment and attempt state are separate:

```text
assignment: queued -> running -> terminal
attempt:    queued -> running -> passed | failed | error | skipped
```

Retry keeps the assignment ID and creates a new `attempt_id` and incremented
`attempt`. Terminal attempt evidence is immutable. A process timeout, missing
or invalid pointer, pointer/publisher mismatch, result-link failure, or
unsupported version makes the attempt `error`; it is never recorded as pass.

Central claim loss or expiry does not signal the runner and does not interrupt
cleanup. Lab finishes the attempt, persists the pointer/evidence, and handles
late Status completion through the coordination contract.

## Compatibility matrix

| Invocation | Behavior |
|---|---|
| Direct, no orchestration metadata | Current direct behavior. |
| Legacy metadata without version | Read as version 1 during the announced window. |
| Explicit version 1 | Version-1 metadata, pointer, and optional manifest. |
| Explicit version 2 | Strict complete v2 validation and required v2 pointer/manifest. |
| Unknown version | Fail before artifact allocation, device construction, or network access. |
| Mixed or incomplete v2 | Fail before artifact allocation, device construction, or network access. |

Readers that accept v2 ship in both repositories before any Lab writer emits
v2. The safe order is:

1. Testcode accepts v1 and v2 but writes a pointer matching its input version.
2. Lab accepts v1 and v2 pointers while continuing to invoke v1.
3. Simulated central-mode Lab invocations begin writing v2 metadata.
4. Version 1 remains available until usage telemetry, rollback proof, and an
   announced retirement window permit removal.

Rollback disables the v2 Lab writer. It does not remove the readers, rewrite
historical attempts, or reinterpret a v1 field with v2 meaning.
