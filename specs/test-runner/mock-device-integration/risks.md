# Mock-device integration — risks and scope

## Scope

### In

- Loopback process/control/native API, simulated Stratum client, scenarios,
  faults, structured events, isolation, privacy canaries, and teardown.

### Out

- Hardware fidelity, firmware/OTA, USB/serial, external networking, performance
  measurement, real credentials, and production use.

## Assumptions

- The current Gamma adapter's bounded AxeOS subset is sufficient for the first
  no-device vertical slice.
- The fake Stratum server remains the deterministic pool authority.
- OS loopback and process signaling are available in local/CI environments.

## Open questions

- WebSocket telemetry can remain optional in the first passing slice; add it to
  the required matrix only when a distributed suite needs that evidence.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Mock diverges from native API | False confidence | adapter fixture/component mismatch | versioned contract and real adapter use |
| Fault timing is nondeterministic | Flaky CI | repeat/component test | synchronized state and bounded explicit counts |
| Simulated miner leaks listener/process | Cross-test interference | teardown/port/PID checks | per-run namespace and exact child cleanup |
| Canaries leak publicly | Privacy regression | recursive public scan | fail-closed sanitization and no raw fallback |
| Simulation mistaken for HIL | Unsupported release decision | evidence metadata/review | label every result simulation |

## Security, privacy, and safety

Loopback-only binding, synthetic data, no device mounts/external network, and
exact child cleanup prevent accidental real-device access. Control APIs are
test-only and never exposed on a production listener.

## Performance and resource risks

Events, fault delays, sockets, and subprocesses can exhaust CI resources.
Contract caps and per-scenario teardown are mandatory; tests fail on overflow.

## Rollout and rollback

Land the process with component tests before using it in the required system
matrix. Rollback removes the integration fixture without changing production
adapter/lifecycle behavior or weakening existing fake-unit tests.
