# Device capability contract — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Abstract device | Define lifecycle, pool, state, log, and path contracts | `src/miner_testcode/devices/base.py:MiningDevice` |
| Capability names | Stable behavior identifiers and missing-set helper | `src/miner_testcode/capabilities.py` |
| Device factory | Map configured type to adapter or fail | `src/miner_testcode/devices/__init__.py:create_device` |
| Normalized state | Portable independently observed mining status | `src/miner_testcode/state.py:DeviceState` |
| Generic test base | Enforce required capability skip before start | `src/miner_testcode/testcase.py:MinerTestCase` |

## Interfaces and contracts

### CLI

- Device selection is owned by configuration/selection; no adapter-specific CLI
  flags are part of this contract.

### Configuration

- `devices[].type` selects a registered adapter. `interfaces` and `options` are
  immutable mappings interpreted by that adapter.

### Environment

- Adapters may consume only explicitly configured environment variable names
  for write-only values or credentials.

### Python API

- `MiningDevice` requires `start`, `ensure_target_firmware`,
  `snapshot_clean_state`, `restore_clean_state`, `configure_pool`,
  `current_info`, `wait_for_stable_state`, `save_device_logs`, and `close`.
- Each adapter exposes `name`, `capabilities`, `state`, and `telemetry`.
- `CleanState` and `PoolSettings` are portable lifecycle inputs.

### HTTP or external protocols

- None at this abstraction. Concrete adapters own transport protocols.

### Files, artifacts, payloads, and persistent state

- Adapter artifacts are rooted in the `TestArtifacts` supplied by the runner.
  Adapters do not choose external publication destinations.

## Contract constraints

### Required invariants

- Advertise a capability only when configured interfaces and implementation can
  honor it.
- Map native state into portable meanings without depending on one firmware's
  lifecycle vocabulary.
- Identity verification precedes mutation.
- Lifecycle and cleanup contracts remain complete even for device-only tests.

### Forbidden behavior

- No model checks in generic tests when capability selection suffices.
- No adapter writes outside explicit methods or supplied artifact root.
- No silent fallback from a required interface to absent evidence.

## Data and state

- `DeviceStateStore` owns successive normalized observations.
- Native raw data may be retained inside local state evidence but publication
  privacy rules still apply.

## Control and data flow

1. Factory constructs adapter from immutable config and test artifact root.
2. Test checks capability set and then drives portable methods.
3. Adapter maps native I/O to normalized state/evidence and owns cleanup.

## Failure and recovery

- Unknown type or invalid required interface → configuration failure.
- Missing test capability → explicit skip.
- Native identity mismatch → device error before mutation.

## Compatibility and migration

- New adapter types are additive registry entries. Removing or renaming a type
  requires profile migration and compatibility notes.
- New abstract methods require every registered adapter and test fake to update
  in one change.

## Resource and operational constraints

- Monitoring remains asynchronous and bounded so one device interface cannot
  block other evidence collection.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Configuration and selection](../configuration-and-selection/SPEC.md) | Selects type and supplies immutable adapter settings. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Defines required failure-safe lifecycle semantics. |
| [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md) | Current concrete implementations. |
| [State, telemetry, and charting](../state-telemetry-and-charting/SPEC.md) | Defines portable observation contracts. |
| [Mock-device integration](../mock-device-integration/SPEC.md) | Validates this contract over loopback through the existing Gamma adapter. |

## Verification approach

- Unit tests cover factory inheritance, identity matching, normalized state,
  capability skips, and model-independent generic behavior.
