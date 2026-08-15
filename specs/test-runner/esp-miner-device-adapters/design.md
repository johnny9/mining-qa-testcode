# ESP-Miner device adapters — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Common AxeOS adapter | API, pool, restart, monitor, telemetry, serial, upgrade, logs, cleanup | `src/miner_testcode/devices/bitaxe.py:BitaxeDevice` |
| Bonanza profile | Require board `1002` and ASIC `BZM` | `src/miner_testcode/devices/bitaxe_bonanza.py` |
| Gamma profile | Require board `602` and ASIC `BM1370` | `src/miner_testcode/devices/bitaxe.py:BitaxeGammaDevice` |
| Type registry | Expose `bitaxe_bonanza` and `bitaxe_602` | `src/miner_testcode/devices/__init__.py` |

## Interfaces and contracts

### CLI

- None beyond generic `--device` selection.

### Configuration

- Required `interfaces.api.base_url`; optional WebSocket, serial, and upgrade
  tables; adapter options include read-only, public label, and optional baseline
  password environment name.
- Gamma OTA uses application and optional web artifacts; it has no bridge
  artifact.

### Environment

- Only configured write-only password variables are adapter inputs.

### Python API

- `BitaxeDevice` implements `MiningDevice`; model subclasses supply identity
  constants and may extend native normalization.
- `Bitaxe602Device` remains a compatibility alias for Gamma.

### HTTP or external protocols

- AxeOS `/api/system/info`, settings PATCH, pause/resume/restart, OTA, and log
  endpoints.
- AxeOS `/api/ws/live` update diffs when enabled.
- ESP USB serial for capture and optional shell-free flash command.

### Files, artifacts, payloads, and persistent state

- API traces exclude bodies. Device state, telemetry, serial, baseline, upgrade,
  and downloaded logs stay under the supplied test artifact directory.

## Contract constraints

### Required invariants

- Exact model identity precedes mutation.
- `mining_active` requires positive hashrate and no pause/fault/overheat or
  blocking lifecycle.
- Pool comparison masks write-only passwords but does not mask identities in
  the in-memory restore baseline.
- Multi-pool IDs and primary/secondary selection survive cleanup.
- Gamma standard telemetry works without Bonanza health extensions.

### Forbidden behavior

- Do not infer a model solely from an API hostname or configured type.
- Do not configure bridge firmware for Gamma 602.
- Do not write masked passwords or redaction markers.

## Data and state

- Native API objects are mapped into `DeviceState`; WebSocket diffs merge into
  a cache while REST remains authoritative for explicit operations.
- Mutation tracking covers write-only fields requiring unconditional restore.

## Control and data flow

1. Read system info and validate board/ASIC.
2. Start serial/monitor/telemetry according to configuration.
3. Map tests into native API operations and normalize observations.
4. Restore mutable state, save logs, and close tasks/interfaces.

## Failure and recovery

- Optional telemetry failure → log once and continue REST polling.
- Required telemetry timeout → device error.
- Restart disconnect → treat as possibly honored, then verify reboot/settings.
- Restore mismatch → cleanup error with bounded mismatch detail.

## Compatibility and migration

- Both flat legacy fields and modern `pools[]` are supported. Schema changes
  need fixture coverage before HIL.

## Resource and operational constraints

- API operations are serialized because concurrent embedded HTTP operations can
  destabilize ESP-Miner. Logs, messages, samples, and retries are bounded.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Device capability contract](../device-capability-contract/SPEC.md) | Defines the portable interface implemented here. |
| [Transport interfaces](../transport-interfaces/SPEC.md) | Supplies bounded native I/O. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Defines pool/pause restore guarantees. |
| [Firmware lifecycle](../firmware-lifecycle/SPEC.md) | Defines configured AxeOS upgrade semantics. |
| [State, telemetry, and charting](../state-telemetry-and-charting/SPEC.md) | Defines normalized observation semantics. |
| [Mock-device integration](../mock-device-integration/SPEC.md) | Emulates the bounded Gamma-native subset for deterministic component/system tests. |

## Verification approach

- Native API fixture tests cover identity, model inheritance, lifecycle
  normalization, WebSocket diff merge, pool schemas, password handling, and
  restore payloads. HIL is required when native contracts change materially.
