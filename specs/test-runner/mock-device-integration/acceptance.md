# Mock-device integration — acceptance

## Functional behavior

- [ ] **TR-MOCK-AC-01:** The loopback process implements the exact
  `mock-device-v1` process, control, AxeOS, state, event, and shutdown contract.
- [ ] **TR-MOCK-AC-02:** A real `bitaxe_602` adapter completes identity, pool
  mutation, restart, fake-Stratum interaction, result production, and verified
  baseline restoration in `pass`.
- [ ] **TR-MOCK-AC-03:** Required failure scenarios deterministically produce
  failed/error outcomes and never a false pass or unbounded wait.
- [ ] **TR-MOCK-AC-04:** Identity mismatch is observed before any write;
  cleanup rejection/mismatch records the restore attempt and remains an error.
- [ ] **TR-MOCK-AC-05:** Reset creates isolated baseline/counters/events and two
  simultaneous mock processes cannot share state, listener, or pool identity.

## Interfaces and compatibility

- [ ] **TR-MOCK-AC-06:** Existing real adapter and fake-Stratum public APIs are
  used without a full-integration-only production branch.
- [ ] **TR-MOCK-AC-07:** Unknown device/control endpoints, OTA, serial,
  filesystem, arbitrary command, and non-loopback binding fail explicitly.

## Quality attributes

- [ ] **TR-MOCK-AC-08:** Bodies, events, waits, reconnects, faults, files,
  listeners, and process shutdown obey exact bounds and clean up after success
  and forced failure.
- [ ] **TR-MOCK-AC-09:** Synthetic privacy canaries are visible in private raw
  evidence but absent from public payloads, URLs, and sanitized logs.
- [ ] **TR-MOCK-AC-10:** Unit/component evidence is labeled simulation and does
  not check or satisfy any HIL acceptance item.

## Verification evidence

- Existing `tests.unit.test_fake_stratum` validates the pool server only; it
  does not satisfy mock-device process criteria.
- `tests.unit.test_specs` validates this proposed feature's structure and
  links; no mock process/component evidence exists yet.

## Acceptance rule

The mock is acceptable only when native API/control/Stratum/component tests and
the Status-owned scenario matrix pass, teardown proves no listener/process
leak, and documentation clearly reports that no physical hardware was tested.
