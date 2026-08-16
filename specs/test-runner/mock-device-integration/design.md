# Mock-device integration — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Mock process | Serve loopback AxeOS/control APIs, simulated miner client, state, and events | `src/miner_testcode/mock_device.py` |
| Real Gamma adapter | Consume the native device API and own lifecycle/cleanup | `src/miner_testcode/devices/bitaxe.py` |
| Fake Stratum server | Supply deterministic jobs/responses and protocol transcript | `src/miner_testcode/interfaces/fake_stratum.py` |
| Runner lifecycle | Select real adapter, capture result/artifacts, and enforce cleanup | `src/miner_testcode/runner.py` and `src/miner_testcode/testcase.py` |

## Interfaces and contracts

### CLI

- The executable and exit semantics follow
  [mock device v1](../../../contracts/mock-device-v1.md).
- Normal `miner-test` CLI uses a generated private profile with type
  `bitaxe_602`; it does not select a special mock adapter.

### Configuration

- Harness supplies loopback base URL, short bounded polling/restart/cleanup
  timeouts, synthetic pool settings, fake-Stratum listener, local publisher,
  and optional local Status publisher.
- No production profile or device coordinate is copied or read.

### Environment

- Only per-run synthetic values are used. Privacy canaries are explicitly
  registered for sanitization tests and never resemble or derive from real
  credentials.

### Python API

- The mock has typed immutable scenario/fault inputs, synchronized state
  transitions, bounded event records, and a minimal Stratum client.
- The existing adapter and fake server APIs remain unchanged unless a generally
  useful testability hook is separately specified.

### HTTP or external protocols

- Device and harness control endpoints, request limits, state, faults, and
  events follow [mock device v1](../../../contracts/mock-device-v1.md).
- The simulated miner implements only the bounded Stratum subset used by the
  current fake server scenarios.

### Files, artifacts, payloads, and persistent state

- Atomic state file publishes selected port/readiness. Bounded JSONL event file
  is structured assertion evidence. Both remain below the harness run directory.
- Testcode outputs normal private/public artifacts and pointer; mock events are
  not automatically published as child evidence.

## Contract constraints

### Required invariants

- Bind loopback only, use OS-assigned ports, and isolate one process/state/pool
  per Lab.
- Full integration constructs the real Gamma adapter and uses normal lifecycle.
- Writes are atomic, ordered, and observable in the event ledger without secret
  values.
- Only successful restart commits pending flat-schema pool settings.
- Final baseline is verified through native `GET /api/system/info`.
- Every fault has bounded count/delay and reset clears it.

### Forbidden behavior

- Do not mount/access `/dev`, USB, serial, Docker socket, production profile,
  external network, or real credentials.
- Do not implement OTA, factory reset, arbitrary command, or filesystem access
  in mock-device v1.
- Do not add model branches to production tests just to accommodate the mock.
- Do not treat a simulated pass as HIL or firmware qualification.

## Data and state

Process/device/mining state machines and event schema are normative in the
mock-device contract. Each reset atomically returns to `gamma-running`, clears
counters/faults/events, and selects one immutable scenario before runner start.

## Control and data flow

1. Start fake Stratum and mock process on loopback; wait for atomic readiness.
2. Reset scenario and generate private runner profile.
3. Run real adapter lifecycle; mock applies native writes/restart and optionally
   connects/submits to fake Stratum.
4. Testcode restores baseline and finalizes result/pointer.
5. Harness reads state/events, asserts ordering/privacy, then stops exact
   processes and verifies listeners closed.

## Failure and recovery

- Invalid config/bind/state path exits nonzero before readiness.
- Fault application is explicit in events; wrong timing/count fails the
  scenario rather than silently continuing.
- SIGTERM performs five-second bounded shutdown; harness may force-stop only the
  exact child PID it created and records cleanup failure.

## Compatibility and migration

Version the mock contract independently from production device APIs. Native API
drift requires updating adapter fixtures and mock in one coordinated Testcode
change. Integration scenarios pin `mock_device_contract_version`.

## Resource and operational constraints

Use the exact contract limits: 64-KiB bodies, 2,000/2-MiB event ledger, 10-second
startup, 5-second shutdown, maximum 2-second injected delay, bounded Stratum
messages/queues/reconnects, and no unbounded sleeps.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Device capability contract](../device-capability-contract/SPEC.md) | The real adapter remains the tested portable boundary. |
| [ESP-Miner device adapters](../esp-miner-device-adapters/SPEC.md) | Defines the native Gamma AxeOS behavior emulated here. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Supplies baseline, restore, error, and final-state semantics. |
| [Stratum V1 regression](../stratum-v1-regression/SPEC.md) | Supplies the existing deterministic fake pool. |
| [Orchestration v2](../orchestration-v2/SPEC.md) | Carries no-device execution evidence through the distributed chain. |

## Verification approach

Unit-test scenario validation/state/faults/events and minimal Stratum client.
Run component tests over actual loopback HTTP with the real Gamma adapter and
fake pool. Then run every Status-owned integration scenario and verify exact
process/listener cleanup. Keep authorized HIL separate.
