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
- Optional PR-specific bounds include `healthy_reconnect_cycles` (3–10) and
  `job_burst_count` (12–64).
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
  set_difficulty, set_extranonce, client.reconnect, BIP310 configure responses,
  and submit behavior needed by the scenarios.

### Files, artifacts, payloads, and persistent state

- Transcript and scenario results are per-run artifacts. They contain method,
  timing, IDs, and sanitized parameters, never raw authorization passwords.

## Contract constraints

### Required invariants

- One class-scoped server and temporary device configuration serve the ordered
  scenario sequence.
- Ordered cases bind to the newest fully negotiated connection after a device
  configuration restart, not a stale pre-restart session.
- Generated ESP-Miner work uses non-empty job IDs shorter than 32 UTF-8 bytes.
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
and injected response modes for the current class. BIP310 configure responses
may be accepted, rejected, or deferred until the test sends the response.
State is reset at defined scenario boundaries, not implicitly between
unrelated messages.

## Control and data flow

1. Start the server and configure the device once.
2. Observe subscribe/authorize and send controlled work.
3. Advance ordered scenarios and record exact transitions.
4. Stop the server and restore the device in class cleanup.

Pool configuration can open a connection immediately before the adapter
reboots the device. Initial handshake validation selects the newest session
and requires a fresh ping response within the existing overall handshake
deadline. Configure, subscribe, authorize, and the first job all use that
same responsive session. An unresponsive pre-reboot socket cannot satisfy
the prerequisite, even if the host has not yet observed its disconnection.

## Failure and recovery

`max_ntime_roll_seconds` defaults to zero and must be an integer from 0 to 120.
An opted-in profile accepts only eight-digit hexadecimal share timestamps at
or after the job timestamp and within that forward allowance. BZM work uses a
60-second hardware timestamp range; its local profile opts into that bound.
The same check applies to ordinary shares and the burst's final clean job.
Valid-work fixture IDs stay below the upstream 32-byte ID storage limit;
oversized IDs are reserved for explicit rejection cases sent as raw
notifications, preserving the valid-job constructor bound.

Standard positive coinbases adjust scriptSig length for the chosen extranonce1
and extranonce2 lengths, including zero-length extranonce2. Fixture construction
rejects invalid sizes and totals that exceed the coinbase scriptSig limit.
Parking work uses the maximum accepted 32-bit pool difficulty. The malformed
large-suffix case is followed by valid work with a 4096-byte output script:
that size is below the firmware suffix capacity and must not itself cause
rejection. The accepted-configure case includes version bits already set in
the job, so share reconstruction must preserve the job's original version.

The zero-length extranonce2 hardware case first obtains a solved ordinary job
with version rolling disabled. It fixes that share's extranonce2 bytes into
the coinbase suffix and uses the solved timestamp for the zero-length job.
This preserves a known solution and the exact transaction bytes, including
scriptSig length. Difficulty, nonce validation, empty submitted extranonce2,
and fresh acceptance remain required. A random finite job is not assumed to
contain a qualifying share.

- Bind/start failure aborts before device mutation where possible.
- Lost client or protocol mismatch fails the current scenario with transcript.
- A malformed line that requires transport recovery must produce a new
  configure/subscribe/authorize handshake within the reconnect bound.
- Lifecycle cleanup still restores the baseline and reports cleanup errors.

## Compatibility and migration

New Stratum messages or firmware behavior must be added as explicit server
capabilities and scenarios. Existing scenario semantics cannot silently widen.
PR-specific cases remain neutral skips unless their PR number is selected.

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

Unit-test fake-server protocol transitions over loopback. Select the PR 1897
device scenarios with `--validation-pr 1897`. Changes to actual miner reactions
require authorized HIL and verified post-test pool restoration.
