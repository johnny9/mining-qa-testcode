# Mining QA orchestration contract v1

This document defines the stable process boundary between
`mining-qa-lab` and `mining-qa-testcode`. The coordinated copy in the other
repository must remain semantically identical. Neither repository imports the
other as a Python package.

## Invocation

The lab invokes the runner executable as:

```text
miner-test --config PROFILE --pattern PATTERN
           [--device NAME ...]
           [--validation-pr NUMBER ...]
```

Exit status `0` means the runner completed successfully. A nonzero status means
failed tests or a runner/configuration error. The result pointer is authoritative
for its more precise `passed`, `failed`, `error`, or `skipped` status when it is
present and valid.

## Environment supplied by the lab

| Name | Contract |
|---|---|
| `MINER_TEST_ORCHESTRATION_METADATA` | Bounded JSON object described below. |
| `MINER_TEST_EXTERNAL_RUN_ID` | Stable assignment identity, opaque to the runner. |
| `MINER_TEST_RESULT_POINTER` | Absolute or worker-local path where the runner atomically writes its pointer. |
| `GITHUB_REPOSITORY` | Repository under test in `owner/name` form. |
| `GITHUB_SHA` | Exact 40-character source commit under test. |
| `GITHUB_REF_NAME` | Branch when known, otherwise empty. |
| `MINER_TEST_PR_NUMBER` | Optional pull-request number, supplied only when applicable. |

The lab passes only its configured environment allowlist plus these explicit
values. SSH execution disables agent forwarding.

## Metadata JSON

Version 1 includes:

```json
{
  "contract_version": 1,
  "gate_id": "firmware-smoke",
  "gate_run_id": "opaque-run-id",
  "gate_definition_digest": "sha256",
  "assignment_id": "opaque-assignment-id",
  "module_id": "public-pool-smoke",
  "platform_key": "bitaxe-gamma-602",
  "setup": "gamma-local",
  "attempt": 1,
  "trigger": {
    "type": "push",
    "branch": "main",
    "pr_number": null
  },
  "gate_result_id": null,
  "gate_result_url": null,
  "testcode": {
    "repository": "johnny9/mining-qa-testcode",
    "ref": "main",
    "commit_sha": "full-40-character-sha"
  }
}
```

`firmware` and `testcode` are present only when those features are active. When
`testcode` is present, the runner must verify that its executing Git repository
and commit match before constructing device objects or contacting hardware.

Readers accept a missing `contract_version` as legacy version 1 during the
repository split. They reject booleans, non-integers, and unknown versions.

## Result pointer written by testcode

The runner atomically replaces the configured path with a bounded UTF-8 JSON
object:

```json
{
  "contract_version": 1,
  "run_id": "runner-run-id",
  "successful": true,
  "status": "passed",
  "artifact_root": "/private/local/path",
  "publishers": [
    {
      "name": "mining_qa_status",
      "success": true,
      "required": true,
      "url": "https://status.example/results/child-id",
      "detail": null
    }
  ]
}
```

- The maximum pointer size is 64 KiB.
- The root must be an object and `publishers` must be a list of objects.
- `status` is one of `passed`, `failed`, `error`, or `skipped`; unknown values
  fail closed as `error`.
- `name`, `success`, and `required` are required publisher fields. `url` and
  `detail` are optional.
- The lab may derive a Mining QA Status child ID from the final path segment of
  a successful `mining_qa_status` publisher URL.
- `artifact_root` is a private diagnostic pointer. The lab does not read those
  artifacts or republish their detailed contents.

For an SSH worker, the lab retrieves at most 64 KiB plus one byte and applies
the same validation locally.

## Ownership and failure rules

- Testcode owns device lifecycle, cleanup, detailed evidence, privacy, source
  provenance, child publication, and atomic pointer writing.
- The lab owns authorization, planning, leases, optional firmware deployment,
  process timeout, private worker log, pointer ingestion, durable assignment
  state, parent publication, and child linking.
- Missing or invalid pointer data, unsupported contract versions, installation
  failures, process/SSH failures, and timeouts produce an assignment error.
- A result-pointer or publication failure never causes the lab to reconstruct a
  detailed child result from private artifacts.

## Compatibility changes

Additive optional fields may ship without a version change. A new required
field, changed meaning, removed value, or incompatible limit requires a new
contract version. Deploy readers that accept both old and new versions before
writers begin requiring the new version. Keep contract fixtures in both
repositories and test each side independently.
