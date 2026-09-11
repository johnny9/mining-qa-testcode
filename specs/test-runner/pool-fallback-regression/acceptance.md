# Pool fallback regression — acceptance

## Functional behavior

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

- [x] **TR-FALLBACK-AC-07:** Loopback and fake-device tests cover timeout,
  stale evidence, partial setup, cleanup failure, secrets, and selection.
- [x] **TR-FALLBACK-AC-08:** An authorized Gamma HIL run validates the module,
  identifies the installed firmware, and independently verifies restoration
  and fresh accepted shares on the original pool.
- [x] **TR-FALLBACK-AC-09:** Cleanup requires new accepted shares after
  restoration; a work-receiving zero-hashrate device may receive one recovery
  restart, which remains an error in the result. Safety faults block that restart.

## Verification evidence

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
- The passing run qualifies the module against installed firmware `9da165d`;
  it does not establish a result for the PR #1962 firmware image. Settings
  edits used the API; frontend pool-form dirty-state handling was not tested.
- Integration onto upstream `5f8bbdb` added the module catalog entry while
  preserving newer runner and Stratum changes. All 127 unit tests and
  wheel/sdist builds passed on that integrated tree. Hardware was not rerun
  after integration; the hardware evidence above comes from the earlier
  working checkout with the same fallback fixture and E2E implementation.

## Acceptance rule

Record unit, package, browser, and hardware evidence separately. A failing
firmware scenario is valid regression evidence, not a passing firmware result.
