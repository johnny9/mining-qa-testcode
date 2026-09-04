# Lifecycle and cleanup — acceptance

## Functional behavior

- [x] **TR-LIFECYCLE-AC-01:** Cleanup is registered before device startup and
  restores captured mutable state after pass, failure, or setup error.
- [x] **TR-LIFECYCLE-AC-02:** Multi-pool selection, SV1/SV2 pool values,
  protocol-specific trust/channel settings, masked passwords, and pause state
  are restored and reread for verification.
- [x] **TR-LIFECYCLE-AC-03:** Redaction markers are rejected during baseline
  capture, pool configuration, and restore before any API write.
- [x] **TR-LIFECYCLE-AC-04:** Restore, log collection, and close failures remain
  visible and make the test result erroneous.

## Interfaces and compatibility

- [x] **TR-LIFECYCLE-AC-05:** Flat and multi-pool device schemas implement the
  same `CleanState` contract.
- [x] **TR-LIFECYCLE-AC-06:** Write-only password changes require an
  environment-provided original and never publish either password.

## Quality attributes

- [x] **TR-LIFECYCLE-AC-07:** Read-only mode detects drift and performs no
  corrective write.
- [ ] **TR-LIFECYCLE-AC-08:** A current authorized HIL run verifies original
  pool/pause restoration and healthy post-cleanup mining on each supported
  hardware family affected by a lifecycle change.

## Verification evidence

- `tests.unit.test_bonanza_lifecycle` — flat/multi-pool SV2 restoration, pool
  validation, write-only password, redaction-marker negative paths, delayed
  reboot detection, and primary-pool alias fallback; reconciled 2026-09-04.
- `tests.unit.test_api.ReadOnlyApiTest` — transport write rejection; reconciled
  2026-08-10.
- Authorized Gamma 602 HIL on 2026-09-04 exercised restoration after both a V1
  scenario error and a fully passing V2 suite. Independent API reads confirmed
  the original pool selection, unpaused mining, and healthy hashrate. AC-08
  remains unchecked because Bonanza 1002 was not covered by this run.

## Acceptance rule

Device-write changes are not acceptable without a pre-write negative test,
restore payload assertion, final-state assertion, and explicit report of
whether HIL restoration was actually performed.
