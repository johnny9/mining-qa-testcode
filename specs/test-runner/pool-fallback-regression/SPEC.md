# Pool fallback regression

Validate pool selection, automatic failover, recovery, and settings edits using
temporary local pools, with optional rendered dashboard and pool-form checks.

- **Lifecycle:** supported
- **Owner:** hardware-test maintainers
- **Last reconciled:** 2026-09-11
- **Spec ID:** TR-FALLBACK

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-11: Extended coverage to active edits, manual fallback preference,
  correcting an unavailable primary, recovery of either pool after a full
  outage, repeated transitions, and connected-but-silent endpoints. Added a
  stable mining window and guarded real-form Save/reload/re-edit validation.
- 2026-09-11: Defined opt-in fallback scenarios and PR 1957/1962 validation,
  temporary-slot cleanup, fresh-share evidence, and optional dashboard checks.
- 2026-09-11: Added fixed-port configuration and post-cleanup mining checks.
  Gamma testing exposed a stalled power state after all test pools were
  unreachable; recovery restarts once and reports an error even when recovery
  succeeds. Initial transition HIL was blocked by incoming test-pool access.
- 2026-09-11: Qualified both hardware cases on Gamma 602 firmware `9da165d`
  using reachable fixed ports. All ten phase checks, rendered dashboard
  observations, and both cleanups passed without a restart. Independent
  verification confirmed original settings and fresh accepted shares.
- 2026-09-11: Integrated with current upstream and registered bounded portable
  options in the module catalog; target configuration remains local.
- 2026-09-11: Expanded Gamma HIL on PR #1962 firmware `ede6c13` passed seven
  cases and exposed a 180-second silent-pool failover failure. Real browser
  saves, active edits, full outages, and repeated cycles passed; all eight
  cleanups restored original mining without a restart.
