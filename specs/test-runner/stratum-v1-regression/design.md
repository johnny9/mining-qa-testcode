# Stratum V1 regression — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Regression case | Own ordered hardware scenarios and device configuration | `tests/e2e/test_stratum_v1_regression.py` |
| Fake server | Implement the supported Stratum subset and capture events | `src/miner_testcode/interfaces/fake_stratum.py:FakeStratumV1Server` |
| Device adapter | Point the miner at the fake endpoint and restore baseline | `src/miner_testcode/devices/base.py` |
| Lifecycle | Guarantee cleanup after setup, test, or teardown failure | `src/miner_testcode/testcase.py:MinerTestCase` |

## Interfaces and contracts

### CLI

- Run through `miner-test`; `--pattern test_stratum_v1_regression.py` selects
  this slice.

### Configuration

- `[tests.stratum_v1_regression]` supplies enablement, bind/advertised host,
  port, username/password, share difficulty, and bounded waits.
- The advertised host must be reachable from the miner; a wildcard bind
  address is not itself a valid advertised endpoint.

### Environment

- No secret environment value is required. Any configured password is treated
  as sensitive even when it is only a fake-pool credential.

### Python API

- `FakeStratumV1Server` exposes bounded start/stop, scenario controls, event
  waits, and a sanitized transcript.

### HTTP or external protocols

- Supported Stratum V1 JSON-RPC includes subscribe, authorize, notify,
  set_difficulty, and submit behavior needed by the scenarios.

### Files, artifacts, payloads, and persistent state

- Transcript and scenario results are per-run artifacts. They contain method,
  timing, IDs, and sanitized parameters, never raw authorization passwords.

## Contract constraints

### Required invariants

- One class-scoped server and temporary device configuration serve the ordered
  scenario sequence.
- Every socket wait, scenario wait, and shutdown is bounded.
- Scenario order is explicit; after the first prerequisite failure, dependent
  scenarios are skipped rather than reported as independent regressions.
- Cleanup owns restoration of the original pool settings.

### Forbidden behavior

- Do not expose the fake server beyond the configured lab interface by default.
- Do not log raw authorization passwords or private pool identities.
- Do not accept arbitrary JSON as proof that the expected protocol transition
  occurred.
- Do not leave the device pointed at the fake server.

## Data and state

The server tracks client connection, authorization, jobs, difficulty, submits,
and injected response modes for the current class. State is reset at the
defined scenario boundaries, not implicitly between unrelated messages.

## Control and data flow

1. Start the server and configure the device once.
2. Observe subscribe/authorize and send controlled work.
3. Advance ordered scenarios and record exact transitions.
4. Stop the server and restore the device in class cleanup.

## Failure and recovery

- Bind/start failure aborts before device mutation where possible.
- Lost client or protocol mismatch fails the current scenario with transcript.
- Lifecycle cleanup still restores the baseline and reports cleanup errors.

## Compatibility and migration

New Stratum messages or firmware behavior must be added as explicit server
capabilities and scenarios. Existing scenario semantics cannot silently widen.

## Resource and operational constraints

The fake server is single-run test infrastructure, not an internet-facing
service. Connections, queues, transcript size, and waits remain bounded.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Transport interfaces](../transport-interfaces/SPEC.md) | Defines bounded protocol transport behavior. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Owns temporary pool restoration. |
| [Artifacts, privacy, and provenance](../artifacts-privacy-and-provenance/SPEC.md) | Sanitizes the protocol transcript. |
| [Public pool smoke](../public-pool-smoke/SPEC.md) | Provides complementary external interoperability evidence. |
| [Mock-device integration](../mock-device-integration/SPEC.md) | Supplies a simulated miner client so the existing fake server can run in full local integration. |

## Verification approach

Unit-test fake-server protocol transitions over loopback. Changes to actual
miner reactions require authorized HIL and verified post-test pool restoration.
