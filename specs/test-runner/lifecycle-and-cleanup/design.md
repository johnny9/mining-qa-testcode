# Lifecycle and cleanup — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Test lifecycle | Register cleanup before start and enforce operation order | `src/miner_testcode/testcase.py:MinerTestCase` |
| Clean-state contract | Define adapter snapshot/restore boundary | `src/miner_testcode/devices/base.py:CleanState` |
| ESP-Miner restore | Snapshot pool/pause state, reject sentinels, restore and verify | `src/miner_testcode/devices/bitaxe.py` |
| Lifecycle regressions | Exercise legacy/new pool schemas, passwords, and marker rejection | `tests/unit/test_bonanza_lifecycle.py` |

## Interfaces and contracts

### CLI

- `runner.cleanup_timeout` bounds restore; normal runner exit becomes
  unsuccessful if cleanup adds an error.

### Configuration

- `devices.options.read_only` forbids mutation at the transport boundary.
- `baseline_stratum_password_env` is required before changing a write-only pool
  password and must resolve in memory.

### Environment

- The configured baseline password environment variable is read only for the
  lifecycle and never included in evidence.

### Python API

- `MiningDevice.start()`, `ensure_target_firmware()`,
  `snapshot_clean_state()`, `restore_clean_state()`, `save_device_logs()`, and
  `close()` are lifecycle extension points.
- `CleanState.settings` and `mining_paused` are the captured mutable contract.

### HTTP or external protocols

- Adapter restore uses native device APIs. A restart is followed by bounded
  online and expected-setting verification.

### Files, artifacts, payloads, and persistent state

- `baseline.json` stores sanitized evidence, never a restore source.
- The in-memory baseline is authoritative for cleanup and may include a
  write-only password supplied from environment.

## Contract constraints

### Required invariants

- Async cleanup is registered before any device operation that can succeed
  partially.
- Target firmware is the run baseline; mutable settings are the per-test
  cleanup baseline.
- Restore is verified by rereading device state.
- Restore, log collection, and close all run even when another cleanup step
  fails.

### Forbidden behavior

- Never use sanitized artifacts as device input.
- Never accept `<redacted>` or `<redacted-pool-identity>` as a pool identity in
  capture, test configuration, or restore.
- Never change a write-only password without a known original.
- Never retry an uncertain write automatically.

## Data and state

- Baseline settings remain in process memory for one test lifecycle.
- Adapter mutation tracking records write-only fields that must be restored
  even when the API masks their current value.

## Control and data flow

1. Adapter creates current native snapshot and sanitized evidence separately.
2. Test may call capability methods that record mutations.
3. Cleanup compares current state, writes only necessary original values,
   restarts when required, verifies state, resumes/pauses as captured, collects
   logs, and closes monitors.

## Failure and recovery

- Invalid baseline → fail before test body mutation.
- Restore timeout or mismatch → test error with mismatch evidence.
- Multiple cleanup failures → `ExceptionGroup`, preserving every failure.

## Compatibility and migration

- Adapters may support both flat and multi-pool APIs, but each must preserve the
  same clean-state semantics.

## Resource and operational constraints

- Cleanup is bounded by `cleanup_timeout`; restart verification is bounded by
  the adapter online timeout.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Device capability contract](../device-capability-contract/SPEC.md) | Defines lifecycle methods adapters must implement. |
| [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md) | Provides current native pool and pause implementation. |
| [Firmware lifecycle](../firmware-lifecycle/SPEC.md) | Firmware becomes the run target before mutable baseline capture. |
| [Artifacts, privacy, and provenance](../artifacts-privacy-and-provenance/SPEC.md) | Sanitized baseline is evidence only. |
| [Mock-device integration](../mock-device-integration/SPEC.md) | Exercises pass, mutation, restart, rejection, mismatch, and cleanup errors over a real adapter boundary. |

## Verification approach

- Fake APIs prove exact outgoing restore payloads and final state.
- Negative tests prove redaction markers and unknown password baselines fail
  before any write.
- Authorized HIL must independently verify the original pool/pause state and
  healthy mining after cleanup.
