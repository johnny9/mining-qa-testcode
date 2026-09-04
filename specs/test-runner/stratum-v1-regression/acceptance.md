# Stratum V1 regression — acceptance

## Functional behavior

- [x] **TR-STRATUM-AC-01:** The fake server deterministically implements the
  supported subscribe, authorize, work, difficulty, and submit flows.
- [x] **TR-STRATUM-AC-02:** Server lifecycle and all protocol waits are bounded.
- [x] **TR-STRATUM-AC-03:** Scenarios have explicit ordering and later dependent
  scenarios skip after the first prerequisite failure.
- [x] **TR-STRATUM-AC-04:** Device configuration uses normal lifecycle cleanup.

## Interfaces and compatibility

- [x] **TR-STRATUM-AC-05:** Bind address and miner-reachable advertised address
  are distinct configuration concepts.
- [x] **TR-STRATUM-AC-06:** The transcript does not retain authorization
  passwords or unsanitized private identity.

## Quality attributes

- [x] **TR-STRATUM-AC-07:** Loopback unit tests cover supported messages,
  injected responses, timeouts, and shutdown.
- [x] **TR-STRATUM-AC-08:** A current authorized HIL run proves the target
  firmware reacts correctly and the original pool is restored.

## Verification evidence

- The complete unit suite passed all 91 tests on 2026-09-04, including local
  Stratum protocol, bounded reconnect, ESP-Miner job-ID, lifecycle, and spec
  integrity coverage. The wheel and sdist also built successfully.
- Authorized Gamma 602/BM1370 HIL against ESP-Miner PR 1897 CI firmware
  `1c44a87` passed its five active ordered cases in artifact
  `20260904T151421.340396Z`; the two PR 1849 validation cases were explicitly
  skipped. Cleanup reported success, and an independent API read confirmed the
  original pools, unpaused mining, and healthy hashrate.
- A broader compatibility run enabling PR 1849's opt-in parser cases is
  retained as artifact `20260904T150022.298245Z`: the five standard cases plus
  fragmentation, consecutive messages, and the exact 16 KiB boundary passed,
  but embedded-NUL reconnect timed out and the dependent invalid-state case
  skipped. This does not invalidate the exact PR 1897 selection, but records a
  current firmware compatibility defect.

## Acceptance rule

Server-only changes may be accepted with loopback tests. Scenario or device
behavior changes require the affected miner model in HIL plus independent
verification that cleanup restored the original pool.
