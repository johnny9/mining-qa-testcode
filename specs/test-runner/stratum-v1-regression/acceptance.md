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
- [x] **TR-STRATUM-AC-09:** The fake server can accept, reject, or defer BIP310
  version-rolling configuration while retaining bounded, sanitized evidence.
- [x] **TR-STRATUM-AC-10:** A current authorized PR 1897 HIL run proves that
  version bits require accepted negotiation, zero-length extranonce2 produces
  accepted work, three healthy server-directed reconnects retain the pool,
  oversized job fields are rejected, and the latest clean job survives a
  bounded burst.

## Verification evidence

- 2026-09-13: Integration regression reproduced the valid-job constructor
  rejecting an intentionally oversized ID before transmission. The malformed
  cases now send raw notifications while positive jobs retain the constructor
  limit. The regression exercises all three rejection inputs and all four
  positive recovery/large-suffix jobs without hardware.

- 2026-09-13: Integrated the Bonanza changes onto current Testcode `main`
  (`629216f`), preserving the newer SV2, restart-detection, privacy, catalog,
  and expanded fallback behavior. All 169 unit tests and wheel/sdist builds
  passed. The hardware runs below used the earlier runner checkout; the
  combined runner has local validation and has not been rerun on hardware.

- 2026-09-13: Network-only Bonanza 1002 / BZM `bzm-cj3-c1758f7` run
  `20260913T044720.196816Z` passed all 12 cases with no failures, errors, or
  skips (294.577 seconds). This includes malformed notifications and state
  messages, accepted/deferred/rejected version negotiation, empty extranonce2,
  three healthy reconnects, rejection of oversized/malformed jobs, acceptance
  of a valid large suffix, and the final clean job in a 24-job burst.
  Independent HTTP verification matched the original settings digest and
  pool rows and observed fresh acceptance at 1200 MHz with no ASIC fault.
  The preserved `ota_0` rollback remained untouched. All 58 reconstructable
  submissions (41 distinct headers) passed independent proof-of-work and
  negotiated-version checks. One raw boundary-successor submission was
  excluded from that audit because its typed job was not recorded. The
  zero-length case reproduced the known seed header. Firmware build and all
  398 QEMU tests passed; runner build and all 110 unit tests passed. This is
  qualification of the recorded Bonanza image with the selected PR scenarios,
  not a claim about another upstream PR artifact or another board.

- 2026-09-13: Fixture unit tests reconstruct complete transactions with
  extranonce2 sizes 0, 8, and 32 and reject invalid fixture bounds. Fixing a
  solved extranonce into the suffix preserves the exact coinbase bytes. All
  110 runner unit tests and wheel/sdist builds passed.

- 2026-09-13: First `bzm-cj3-c1758f7` run `20260913T043738.858976Z`
  passed eight cases, timed out on the unseeded zero-length extranonce2 job,
  and skipped three dependents. No hardware fault occurred. Independent
  cleanup verification matched the original settings and observed a fresh
  accepted share. All 34 reconstructable submissions passed an independent
  SHA-256 audit; the raw boundary-injection successor was not retained as a
  typed job and was excluded from that audit. A subsequent fixture correction
  preserves a known solution for the finite zero-extranonce search space.

- 2026-09-13: Network-only Bonanza `bzm-cj2-c1758f7` run
  `20260913T034510.465929Z` passed six cases, failed malformed-notify
  rejection, and skipped five dependent cases. A non-hex previous hash
  increased `workReceived` from 3 to 4. This is a firmware parser failure,
  separate from the clean-job rotation fix; AC-08 and AC-10 were unchecked
  after that historical run.
  Original settings were restored without a cleanup error. All 107 runner
  unit tests and wheel/sdist builds passed after the session-selection fix.

- 2026-09-13: A two-connection loopback regression reproduced selection of the
  old pre-reboot handshake. Session selection now requires a responsive
  current connection; an unresponsive historical handshake times out.

- 2026-09-13: `tests.unit.test_validation_tests.StratumTimestampTest` verifies
  strict defaults, the BZM forward allowance, malformed/backward/excessive
  timestamp rejection, and invalid configuration bounds.

- `tests.unit.test_fake_stratum` and `tests.unit.test_stratum` cover local
  protocol behavior. The focused fake-server suite, including BIP310 response
  control, passed on 2026-08-30.
- 2026-09-13: Network-only Bonanza PR #5 run `20260913T012006.781242Z`
  passed setup, subscribe, authorize, and a valid accepted share. Difficulty
  change timed out because the positive fixture used an overlong job ID;
  remaining dependent scenarios skipped. At that point, shortened fixture
  IDs had only unit validation; the later run above passed the difficulty
  change on hardware. Subsequent fallback HIL hit
  runtime fault 4103, blocking further qualification. Original settings and
  healthy mining were verified after rollback to the preserved firmware.
  AC-08 and AC-10 were unchecked after that historical run.
- The complete unit suite passed all 103 tests on 2026-09-04, including local
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
