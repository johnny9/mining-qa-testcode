# Firmware lifecycle — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Device upgrade coordinator | Validate config, choose OTA/USB, order artifacts, verify result | `src/miner_testcode/devices/bitaxe.py:ensure_target_firmware` |
| HTTP uploader | Paced bounded binary transfer without write retry | `src/miner_testcode/interfaces/api.py` |
| Serial flasher | Resolve port and execute shell-free configured command | `src/miner_testcode/interfaces/serial.py` |
| Upgrade evidence | Record artifact role/hash/size and operation outcome | `src/miner_testcode/devices/bitaxe.py` |

## Interfaces and contracts

### CLI

- No direct firmware flag; target is profile-controlled to keep runs
  reproducible.

### Configuration

- `devices.interfaces.upgrade.enabled`, `method`, `expected_version`, artifact
  paths, timeouts, pace/chunk parameters, and method-specific roles.
- OTA accepts application and optional web; USB uses configured command and
  required artifact placeholders. Gamma has no bridge artifact.

### Environment

- None. Firmware paths are local configuration, not secret environment values.

### Python API

- `MiningDevice.ensure_target_firmware()` is called before baseline capture.
- Adapter path resolution is relative to the profile project directory.

### HTTP or external protocols

- AxeOS OTA endpoints receive raw application/web artifacts. Web is installed
  before application so the application reboot occurs last.
- USB flash uses an explicit argv template and stable resolved port.

### Files, artifacts, payloads, and persistent state

- Input artifacts remain local files. Upgrade evidence records role, basename,
  size, and SHA-256 without embedding binaries.
- Target firmware becomes the run baseline and is not automatically rolled back.

## Contract constraints

### Required invariants

- Upgrade is disabled by default and only runs from explicit profile intent.
- Artifact existence, role, and method validate before the first write.
- OTA uploads are paced/bounded and not automatically retried.
- Same hardware identity and expected version are verified after reboot.

### Forbidden behavior

- Do not flash an artifact inferred only by filename or downloaded ad hoc.
- Do not use factory/merged images for application OTA.
- Do not claim rollback that was not executed.
- Do not configure bridge artifacts for Gamma 602.

## Data and state

- Current and expected versions are transient setup state.
- Evidence is per-test/run; firmware remains on the device after cleanup.

## Control and data flow

1. Validate current identity/version and every configured local artifact.
2. Apply ordered method-specific writes once.
3. Observe offline/online transition and require expected identity/version.

## Failure and recovery

- Uncertain upload response → do not retry; poll identity/version to determine
  actual state or fail.
- Device does not return → setup error; operator uses documented recovery
  artifact/method.
- Wrong returned identity/version → fail before tests.

## Compatibility and migration

- New artifact roles or methods require explicit adapter support, example
  configuration, negative tests, and migration notes.

## Resource and operational constraints

- Artifact size, chunk size, pace, response size, and reboot wait are bounded.
  Flashing requires exclusive physical device access.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Upgrade precedes mutable baseline; firmware is not per-test cleanup state. |
| [Transport interfaces](../transport-interfaces/SPEC.md) | Supplies bounded OTA and serial execution. |
| [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md) | Owns artifact roles and model identity. |
| [Lab artifact deployment](https://github.com/johnny9/mining-qa-lab/blob/main/specs/lab-orchestrator/artifact-resolution-and-deployment/SPEC.md) | External lab can install exact CI artifacts before runner execution. |

## Verification approach

- Unit/config tests cover invalid roles/methods and transport boundaries where
  practical. Real upload/order/version behavior requires explicit HIL with a
  known rollback path.
