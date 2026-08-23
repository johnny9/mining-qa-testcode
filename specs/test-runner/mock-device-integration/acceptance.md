# Mock-device integration — acceptance

## Functional behavior

- [x] **TR-MOCK-AC-01:** The loopback process implements the exact
  `mock-device-v1` process, control, AxeOS, state, event, and shutdown contract.
- [x] **TR-MOCK-AC-02:** A real `bitaxe_602` adapter completes identity, pool
  mutation, restart, fake-Stratum interaction, result production, and verified
  baseline restoration in `pass`.
- [x] **TR-MOCK-AC-03:** Required failure scenarios deterministically produce
  failed/error outcomes and never a false pass or unbounded wait.
- [x] **TR-MOCK-AC-04:** Identity mismatch is observed before any write;
  cleanup rejection/mismatch records the restore attempt and remains an error.
- [x] **TR-MOCK-AC-05:** Reset creates isolated baseline/counters/events and two
  simultaneous mock processes cannot share state, listener, or pool identity.

## Interfaces and compatibility

- [x] **TR-MOCK-AC-06:** Existing real adapter and fake-Stratum public APIs are
  used without a full-integration-only production branch.
- [x] **TR-MOCK-AC-07:** Unknown device/control endpoints, OTA, serial,
  filesystem, arbitrary command, and non-loopback binding fail explicitly.

## Quality attributes

- [x] **TR-MOCK-AC-08:** Bodies, events, waits, reconnects, faults, files,
  listeners, and process shutdown obey exact bounds and clean up after success
  and forced failure.
- [x] **TR-MOCK-AC-09:** Synthetic privacy canaries are visible in private raw
  evidence but absent from public payloads, URLs, and sanitized logs.
- [x] **TR-MOCK-AC-10:** Unit/component evidence is labeled simulation and does
  not check or satisfy any HIL acceptance item.

## Verification evidence

- `tests/integration/test_integration_smoke.py` ran through the normal runner in
  every applicable two-Lab scenario on 2026-08-16. It used the real Gamma 602
  adapter, pool mutation/restart, real fake-Stratum server, deterministic share,
  Testcode cleanup, child result, and pointer path.
- The Status-owned nine-scenario simulation passed two independent mock
  processes and exact-PID/listener teardown, including pass, deterministic
  failure, cleanup rejection, malformed/private pre-device rejection, replay,
  expiry, and restart.
- `tests.unit.test_mock_device` directly covers scenario locking, every bounded
  fault shape, identity/no-write behavior, HTTP/malformed/restart failures,
  cleanup rejection and mismatch, rejected-share and Stratum-disconnect paths,
  unsupported operations, non-loopback/symlink refusal, reset isolation, and
  private raw canary capture. All eight component cases passed on 2026-08-16.
- `tests.unit.test_sanitized_log` and the Status-owned scenario evidence prove
  that those private canaries are absent from the digest-addressed public copy,
  pointer/result payload, and public Status data.

## Acceptance rule

The mock is acceptable only when native API/control/Stratum/component tests and
the Status-owned scenario matrix pass, teardown proves no listener/process
leak, and documentation clearly reports that no physical hardware was tested.
