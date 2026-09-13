# Pool fallback regression — acceptance

## Functional behavior

- [x] **TR-FALLBACK-AC-16:** The separate SV2 module runs all shared fallback
  scenarios in standard and extended channels with authenticated endpoints,
  current worker/channel-bound accepted shares, and original settings restored.
- [x] **TR-FALLBACK-AC-17:** SV2 complete silence suppresses jobs, share ACKs,
  and reconnect handshakes; short silence preserves the same Noise connection,
  and sustained silence fails over and recovers within bounded phases.
- [x] **TR-FALLBACK-AC-01:** Manual primary/fallback selection and automatic
  failover/recovery require matching preference/active flags plus fresh work,
  a new submission at the expected server, and device acceptance progression.
- [x] **TR-FALLBACK-AC-02:** Full settings saves during fallback and primary/
  secondary swaps eventually mine on the correct endpoint with saved edits;
  either probing or reconnecting may succeed.
- [x] **TR-FALLBACK-AC-03:** Original pool rows and passwords are never sent to
  fake pools or rewritten; temporary rows are removed after every outcome.
- [x] **TR-FALLBACK-AC-04:** Cleanup restores and verifies selection, pause,
  and unchanged operating settings; errors remain visible to the runner.

## Interfaces and compatibility

- [x] **TR-FALLBACK-AC-05:** Enablement is explicit; PR cases retain normal
  validation selection; invalid/read-only profiles and unsupported pool tables
  fail or skip before mutation.
- [x] **TR-FALLBACK-AC-06:** Optional browser validation reads the actual
  dashboard dropdown and uses its controls for manual switching. API-only
  evidence makes no frontend claim.

## Quality attributes

- [x] **TR-FALLBACK-AC-10:** Browser form edits and swaps in both directions
  survive Save, reload, and a subsequent edit; original rows and masked
  passwords are excluded by a fail-closed request guard.
- [x] **TR-FALLBACK-AC-11:** Active-pool edits without role swaps, correcting an
  unavailable primary, and saves with manually preferred fallback resume
  mining with the edited identity and intended preference.
- [x] **TR-FALLBACK-AC-12:** After a bounded outage of both endpoints, restoring
  either endpoint resumes mining without a manual restart.
- [x] **TR-FALLBACK-AC-13:** Repeated failover/recovery requires stable
  fresh-share progression after each transition.
- [x] **TR-FALLBACK-AC-14:** A connected primary that stops replying triggers
  failover within the configured deadline and recovers when replies resume.
- [x] **TR-FALLBACK-AC-15:** A 15-second primary silence resumes fresh mining
  on the same connection; long-silence validation uses a separate bounded
  deadline that accommodates the firmware's inactivity timeout and retries.

- [x] **TR-FALLBACK-AC-07:** Loopback and fake-device tests cover timeout,
  stale evidence, partial setup, cleanup failure, secrets, and selection.
- [x] **TR-FALLBACK-AC-08:** An authorized Gamma HIL run validates the module,
  identifies the installed firmware, and independently verifies restoration
  and fresh accepted shares on the original pool.
- [x] **TR-FALLBACK-AC-09:** Cleanup requires new accepted shares after
  restoration; a work-receiving zero-hashrate device may receive one recovery
  restart, which remains an error in the result. Safety faults block that restart.

- [x] **TR-FALLBACK-AC-18:** Increasing locally validated results defer a
  zero-hashrate recovery restart during `MINING`; an unchanged count does not.
  Progress alone cannot pass cleanup without nonzero hashrate and a fresh
  accepted share. ASIC health faults prevent the restart.

## Verification evidence

- 2026-09-13: Integrated the Bonanza changes onto current Testcode `main`
  (`629216f`), preserving the newer SV2, restart-detection, privacy, catalog,
  and expanded fallback behavior. All 169 unit tests and wheel/sdist builds
  passed. The hardware runs below used the earlier runner checkout; the
  combined runner has local validation and has not been rerun on hardware.

- 2026-09-13: After Stratum admission and negotiation fixes, Bonanza 1002 /
  BZM `bzm-cj3-c1758f7` passed both network-only cases and all ten phases in
  run `20260913T045349.393527Z` (230.530 seconds), with no failures, errors,
  or skips. All 18 submissions passed an independent SHA-256 audit. Final
  independent HTTP verification matched the original settings digest and
  pool rows and observed a new accepted share at 1449.86 GH/s and 1200 MHz,
  with no ASIC fault. Rollback `ota_0` remained preserved. This run makes no
  Gamma or browser claim.

- 2026-09-13: Bonanza 1002 / BZM firmware `bzm-cj2-c1758f7` passed both
  API-only hardware cases in run `20260913T033138.656768Z` (322.479 seconds),
  with all ten phases and both cleanups passing without a recovery restart.
  Original pool rows, operating settings, and fresh accepted shares were
  verified. All 17 captured submissions also passed an independent SHA-256
  audit. The final 107-test unit suite, spec integrity, wheel/sdist builds, and
  whitespace checks passed. No current Gamma/browser result is claimed.

- 2026-09-13: Additional network-only Bonanza clean-job stress run
  `stress-20260913T035301Z` passed startup through 1200 MHz, a 24-job clean
  burst, and a 120-second soak with 142 jobs and 27 independently verified
  shares. All 114 health samples had no hardware fault. Cleanup restored the
  original settings and fresh accepted shares without a recovery restart.
  A subsequent independent HTTP check matched the original settings digest,
  found only the original pool rows, and observed another accepted share at
  1400.99 GH/s. The known-good `ota_0` firmware remained preserved.

- 2026-09-13: A fake Bonanza warmup reproduced the premature restart before
  the fix. New tests cover live progress, an unchanged counter, missing final
  shares/hashrate, and ASIC health faults. The existing Gamma/browser and expanded fallback qualifications below
  have not been rerun for this change. This Bonanza run covered the two
  original API cases, not the newer nine-case module or SV2 scenarios.

- 2026-09-11: Gamma-02 / BM1370 HIL run `20260911T215406.340854Z` used clean
  testcode `df990b1e1a468b3d0c328c0f52ceafa87a3784a9` and current master
  `1df7ba1ec12833045693cf1352042e8d78628c22`. All 18 cases passed in
  2644.904 seconds, with zero failures, errors, or skips: nine cases and
  37 passing mining phases for each channel type. This includes real browser
  saves, full outages, repeated transitions, settings edits, and both silence
  cases. The short silence retained the same encrypted connection in each mode.
- Extended-channel silent failover reached stable fallback mining after
  225.064 seconds and recovered primary after 58.574 seconds. Standard-channel
  failover took 224.766 seconds and recovery 27.133 seconds. Each trace showed
  one receive failure followed by three failed Noise handshake retries.
  These are measured complete-silence results, not required exact timings.
- All 18 cleanups restored original settings and fresh shares without a
  recovery restart. Independent verification confirmed the two original rows,
  fresh accepted shares, 974.88 GH/s and 60.125 degrees C on master. All 70
  channel-open requests and 1,194 submissions in the saved transcripts matched
  the channel type requested by their case. This completes AC-16 and AC-17.
- After that run, the mining-evidence predicate was strengthened to reject a
  wrong negotiated channel type. Hardware traces were audited explicitly for
  the same condition; the new predicate is separately covered by positive and
  negative unit tests. The full hardware run above remains pinned to `df990b1`.
  All 146 final unit tests, wheel/sdist builds, and specification checks passed.
- The prior firmware `8cdade8b` and original pool configuration were restored
  after SV2 HIL, with reboot and fresh accepted shares independently verified.
  The final read measured 1118.81 GH/s and 59.875 degrees C. All 229 finalized
  run files passed the private-coordinate/original-worker audit; private raw
  logs remain separate. Both test listeners and the browser were closed.
- 2026-09-11: All 145 unit tests passed after adding SV2 fallback coverage.
  New tests cover both authenticated channel modes, ACK-bound worker evidence,
  nonce continuity through silence, silent reconnect handshakes, preserved
  ports/authorities after outages, explicit resource errors, invalid settings,
  partial setup cleanup, privacy, and discovery of exactly 18 SV2 cases.
  Wheel/sdist and specification integrity checks passed. SV2 HIL was pending
  at that step; it is qualified by the later run recorded above.
- 2026-09-11: The silent-pool fix validation adds separate long-silence budget
  forwarding, invalid catalog bounds, and short-silence fault-release checks.
  All 138 unit tests and wheel/sdist builds passed. The new hardware case and
  longer failover budget are qualified by the final fix run below; earlier
  hardware evidence describes the previous module and firmware.
- 2026-09-11: `tests.unit.test_pool_fallback` passed 23 tests covering pool
  ownership, partial writes, cleanup failure, policy-independent mining checks,
  privacy, loopback jobs, browser attachment, resource limits, and recovery.
- Gamma 602 / BM1370 firmware `9da165d` was identified and tested with browser
  observation and serial capture. Incoming connections to the local fake pools
  timed out, so the transition scenarios did not reach their prerequisites.
- The failed setup restored the original table, selection, and operating
  settings. The installed firmware required a recovery restart before hashing
  and new accepted shares resumed. This is not successful transition HIL.
- AC-01, AC-02, AC-06, and AC-08 were left unchecked after the initial blocked
  runs, pending reachable test pools and completed transition/browser scenarios.
- Final verification: all 91 unit tests, specification integrity, wheel/sdist
  builds, and whitespace checks passed. Finalized hardware artifacts contained
  no raw target/test-host IP or target MAC matches in the coordinate audit.
- Hardware run `20260911T015832.203679Z` verified automatic cleanup recovery:
  the setup timeout and required restart remained errors, original settings
  were restored, and an independent check observed 1097 GH/s and new accepted
  shares on the original pool. The opt-in PR case was skipped in that focused
  cleanup run; no successful transition qualification is claimed.
- Hardware run `20260911T024451.766442Z` completed on Gamma 602 / BM1370
  firmware `9da165d`: two tests passed, zero failures/errors/skips, in 231.446 s.
  Reachable fixed ports enabled all ten phase checks, including manual
  selection, automatic failover/recovery, settings saves during fallback,
  edited pool-role swaps, and an unavailable preferred fallback. Every phase
  included the rendered dashboard label and fresh accepted-share evidence.
- Both cases restored the original pool table and operating settings, resumed
  accepted shares, and required no recovery restart. Independent verification
  confirmed only the two original rows remained and measured 1049.30 GH/s,
  59.625 degrees C, and new accepted shares. Finalized artifacts passed the
  private-coordinate audit. This completes AC-01, AC-02, AC-06, and AC-08.
- That earlier run qualifies the module against installed firmware `9da165d`;
  it does not establish a result for the PR #1962 firmware image. Settings
  edits used the API; frontend pool-form dirty-state handling was not tested.
- Integration onto upstream `5f8bbdb` added the module catalog entry while
  preserving newer runner and Stratum changes. All 127 unit tests and
  wheel/sdist builds passed on that integrated tree. Hardware had not yet been
  rerun at that integration step; the hardware evidence above comes from the earlier
  working checkout with the same fallback fixture and E2E implementation.
- Subsequent PR #1962 run `20260911T030633.163670Z` passed both original cases
  and all ten phase checks on Gamma 602 firmware `ede6c13`, in 141.998 s with
  zero failures, errors, or skips. The image came from CI merge
  `ede6c132653288553479de4e952885873f184eec`, containing PR head
  `13d7246b593865b2d8f8cf2600c8c6deb221c59d`. Both cleanups required no restart;
  independent verification confirmed original settings and fresh shares.
- Expanded-module unit verification passed all 136 tests, including browser
  request rejection and payload preservation, real TCP silence, resetting the
  stability window, and releasing silence before failed-phase cleanup.
- Expanded PR-firmware run `20260911T040734.262065Z` completed all eight cases
  on Gamma 602 / BM1370 firmware `ede6c13`: seven passed, one failed, zero
  errors or skips, in 1142.423 s. There were 33 passing mining phases. Real
  browser validation completed three guarded saves, both role swaps, reload,
  and re-edit persistence. Active edits, both independent 45-second full
  outages, and all three failover/recovery cycles passed. This completes
  AC-10 through AC-13.
- In that historical run, AC-14 remained unqualified: the silent connected primary retained selection
  for 180 s while accepted shares remained at six. Fallback received no fresh
  submissions; recovery after that assertion was not reached. The regression
  remains a failure, with no skip or expected-failure conversion. Source
  inspection found the same SV1 receive-loop blob before and after #1962;
  that points to an existing limitation, not a demonstrated new PR defect.
- All eight cleanups restored original settings and fresh shares without a
  restart. Independent verification confirmed the two original rows and
  new accepted shares at 1156.29 GH/s and 59.75 degrees C. The browser and
  listeners were closed. All 106 finalized artifact files passed an audit for
  target/test-host addresses, target MAC, and original pool worker names.
- Wheel/sdist builds include the browser helper and expanded module catalog.
  Specification integrity, maintenance review, and whitespace checks passed.
- Final fix run `20260911T153046.664704Z` used testcode
  `a5bec343f3fa40821da12a98e7d497461c526ebc` and firmware
  `8cdade8b7b3f48fdc3f828e87b080b69806a3e56` (ESP-Miner #1964 fix), based on
  merged #1962. All nine cases and 37 mining phases passed in 1795.388 s,
  with zero failures, errors, or skips. The 15-second silence retained the
  same primary connection and resumed accepted shares. Sustained silence
  produced four bounded receive timeouts, reached stable fallback mining in
  732.392 s, and recovered primary mining in 53.835 s after replies resumed.
  These timings include the unchanged three-minute receive and retry policy.
  This completes AC-14 and AC-15.
- All nine fix-run cleanups restored original settings and fresh shares
  without a restart. Independent verification confirmed the two original
  rows, fresh accepted shares, 1078.03 GH/s and 60.375 degrees C. The browser
  and test listeners were closed. All 118 finalized run artifact files passed
  the private-coordinate and original-worker audit; private raw logs remain
  in their separate, unpublished directory.

## Acceptance rule

Record unit, package, browser, and hardware evidence separately. A failing
firmware scenario is valid regression evidence, not a passing firmware result.
