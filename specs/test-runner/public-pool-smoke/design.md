# Public pool smoke — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Smoke case | Resolve settings, coordinate probe/configuration, assert mining stability | `tests/e2e/test_public_pool_smoke.py` |
| Stratum probe | Independently subscribe, authorize, and receive jobs | `src/miner_testcode/interfaces/stratum.py` |
| Device adapter | Configure/verify pool, restart, normalize state, restore baseline | `src/miner_testcode/devices/base.py`, `src/miner_testcode/devices/bitaxe.py` |
| Telemetry | Record probe/start/stability milestones and samples | `src/miner_testcode/telemetry.py` |

## Interfaces and contracts

### CLI

- Run through normal `miner-test`; `--pattern test_public_pool_smoke.py` narrows
  the module.

### Configuration

- `[tests.public_pool_smoke]`: host, port, TLS, username/password sources,
  optional separate probe identity, configure flags, difficulty, minimum
  hashrate, work-age, readiness, stable samples, jobs, probe timeout, and
  accepted-share policy.
- `configure_device=false` pairs with read-only operation when the existing
  device pool already matches.
- In reconfiguration mode, an explicit or environment-provided device username
  takes precedence; otherwise the current device pool username is preserved.

### Environment

- Username/password default to `MINER_TEST_POOL_USER` and
  `MINER_TEST_POOL_PASSWORD` or configured variable names.
- The username environment variable is optional when reconfiguration can
  preserve a non-empty username from the device baseline.
- Password is not written unless explicitly enabled and a restorable baseline
  password exists.

### Python API

- `PublicPoolSmokeTest` requires API, mining state, pool configuration, and
  Stratum V1 capabilities.

### HTTP or external protocols

- Stratum V1 TCP/TLS probe and device-native pool/state API.

### Files, artifacts, payloads, and persistent state

- `stratum-probe.json`, device state/telemetry, logs, and result records remain
  under the run. Identities/passwords are sanitized before publication.

## Contract constraints

### Required invariants

- Probe identity may be public/disposable and independent of the device's
  private payout identity.
- A disposable probe identity is never substituted for the device's current
  payout identity during reconfiguration.
- Probe runs concurrently with device observation and is cancelled/collected
  on cleanup.
- Stable health requires consecutive fresh samples, minimum hashrate, no fault,
  active mining, correct pool, and recent work.
- Accepted share is optional unless explicitly configured.

### Forbidden behavior

- Do not log/publish private payout identity or password.
- Do not mutate a read-only device.
- Do not claim pool health from the device API alone without independent
  protocol evidence.
- Do not treat public pool availability as deterministic hardware behavior.

## Data and state

- Probe result and stable state samples are per-test evidence.
- Temporary device pool settings are owned by the lifecycle baseline/restore.

## Control and data flow

1. Start independent probe and optional temporary device configuration.
2. Observe normalized state until stable-window predicate holds.
3. Await probe job result, save structured evidence, and let lifecycle restore.

## Failure and recovery

- Probe timeout/failure → test fails; probe task is cancelled/collected.
- Device health timeout → latest state remains in error/evidence.
- Pool configuration changed → lifecycle restore/restart verifies original.

## Compatibility and migration

- New pool protocol requirements need probe and device capability updates.
  Defaults must retain non-share-dependent smoke semantics.

## Resource and operational constraints

- External pool/network behavior is variable. All probe/readiness/stability
  waits are bounded and the test does not flood the pool.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Configuration and selection](../configuration-and-selection/SPEC.md) | Supplies pool/test settings and secrets. |
| [Transport interfaces](../transport-interfaces/SPEC.md) | Supplies independent Stratum probe. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Restores any temporary device pool. |
| [State, telemetry, and charting](../state-telemetry-and-charting/SPEC.md) | Defines stable health and evidence. |

## Verification approach

- Unit-test the probe protocol independently. The complete acceptance outcome
  requires authorized HIL against the configured device/pool and independent
  post-cleanup verification.
