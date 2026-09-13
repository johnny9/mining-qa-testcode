# Lifecycle and cleanup

Own one failure-safe device lifecycle and restore every mutable setting a test
is allowed to change.

- **Lifecycle:** supported
- **Owner:** test-runner maintainers
- **Last reconciled:** 2026-09-13
- **Spec ID:** TR-LIFECYCLE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-13: Wait for staged Bonanza startup before treating a reboot as ready;
  safety faults fail before any cleanup resume request.
- 2026-09-04: Hardened restart readiness against transient API failures and
  pre-reboot zero uptime, and resolved missing flat settings aliases through
  the selected primary pool.
- 2026-09-04: Extended pool baselines and verified cleanup to include SV2
  protocol, channel, authority, and authentication fields.
- 2026-08-14: Linked deterministic mock-device cleanup/error scenarios for
  no-hardware component and system integration.
- 2026-08-10: Added the fail-closed redaction-marker baseline/write contract
  and reconciled lifecycle ordering and cleanup error semantics.
