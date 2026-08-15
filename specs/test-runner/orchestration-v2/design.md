# Orchestration v2 — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Metadata parser | Select contract version, validate strict v2 and environment equality | `src/miner_testcode/config.py` |
| Provenance guard | Verify executing Testcode repository/SHA before artifacts/devices | `src/miner_testcode/provenance.py` |
| Runner | Freeze correlation, drive lifecycle, build manifest, and write matching pointer | `src/miner_testcode/runner.py` |
| Result/publishers | Serialize allowlisted public v2 correlation and child identity | `src/miner_testcode/results.py` and `src/miner_testcode/publishers.py` |
| Privacy formatter | Reject private identity/canaries and sanitize distinct log artifacts | `src/miner_testcode/redaction.py` |

## Interfaces and contracts

### CLI

- Existing `miner-test --config --pattern [--device] [--validation-pr]` remains
  unchanged. Contract version comes only from bounded orchestration metadata.

### Configuration

- Existing profile/device/test/publisher selection remains private and cannot
  be supplied by central metadata. Publisher origin must match the v2 result
  URL policy.

### Environment

- Exact variables and cross-field equality follow
  [orchestration v2](../../../contracts/orchestration-v2.md).
- Resolved secrets remain environment-only and cannot enter correlation,
  results, logs, manifests, or pointer publisher details.

### Python API

- One immutable version-tagged metadata model exposes explicit public and
  private serializers.
- Pointer construction accepts that frozen model and finalized runner/publisher
  state; it cannot read mutable process-global correlation.

### HTTP or external protocols

- Mining QA child publication adds the exact allowlisted v2 `orchestration`
  section. Status independently verifies it.
- No coordination/pull HTTP client is added to Testcode.

### Files, artifacts, payloads, and persistent state

- Private pointer, required v2 manifest, public child section, and sanitized
  log metadata use the exact contract bounds.
- Raw logs remain in private bounded staging; sanitized log is a newly created
  immutable artifact with sanitizer version, size, and SHA-256.

## Contract constraints

### Required invariants

- Validate contract/environment/Testcode provenance before artifact allocation,
  device factory, transport, or publisher.
- Preserve every ID exactly and keep `local_gate_run_id` private.
- Construct public payloads from allowlisted fields; pointer and public child
  are separate serializers.
- Required publisher result ID/URL must match the pointer and public origin.
- Manifest finalization precedes atomic pointer replacement.
- Cleanup and privacy failure can never be represented as pass.

### Forbidden behavior

- Do not accept central profiles, device selectors, paths, commands, or
  credentials.
- Do not infer absent/mismatched correlation or silently coerce wrong types.
- Do not publish private pointer fields, raw logs, or redaction markers as
  structured identities.
- Do not publish global/parent gate status.

## Data and state

Validated metadata is immutable for one invocation. Runner `run_id` is created
once. Detailed results and publisher records are finalized before manifest and
pointer; the public orchestration section and private pointer share typed source
data but not a common broad serializer.

## Control and data flow

1. Parse version, validate strict schema/environment, verify exact checkout.
2. Allocate artifacts, construct selected device, and run existing lifecycle.
3. Finalize result, sanitize/publish child evidence and optional sanitized log.
4. Build/verify manifest and atomically write the matching private pointer.

## Failure and recovery

- Preflight mismatch exits configuration/infrastructure failure without device
  access.
- Lifecycle/cleanup/publisher/manifest/pointer failures remain explicit errors.
- Lab handles process retry and central expiry; Testcode never retries itself or
  changes assignment/attempt identity.

## Compatibility and migration

Parser and pointer writer remain version aware. Ship v2 Testcode reader/writer
dormant, then Lab v2 pointer reader, then enable simulated Lab metadata writer.
Rollback disables Lab v2 input while retaining both Testcode readers.

## Resource and operational constraints

Metadata/pointer are 64 KiB, manifest is 256 KiB/512 entries/50 MiB per file/
512 MiB total, publisher list is at most 16, and all strings/network bodies/
uploads/retries/timeouts retain explicit bounds.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Configuration and selection](../configuration-and-selection/SPEC.md) | Owns pre-device selection and environment validation. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Cleanup truth remains authoritative. |
| [Artifacts, privacy, and provenance](../artifacts-privacy-and-provenance/SPEC.md) | Owns exact-source and public/private evidence. |
| [Result model and publishing](../result-model-and-publishing/SPEC.md) | Owns child payload, publisher policy, manifest, and pointer. |
| [Lab central coordination agent](https://github.com/johnny9/mining-qa-lab/blob/main/specs/lab-orchestrator/central-coordination-agent/SPEC.md) | Supplies v2 input and consumes the pointer. |

## Verification approach

Use valid/invalid fixtures for every primitive and correlation mismatch; prove
pre-device ordering with fakes; inspect pointer/public payload equality and
privacy canaries; cover every outcome/publisher/cleanup failure; then run the
Status-owned two-Lab integration matrix.
