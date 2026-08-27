# Public pool smoke

Verify independent Stratum reachability and stable live mining against a
configured public pool without requiring a share in a short window.

- **Lifecycle:** supported
- **Owner:** hardware-test maintainers
- **Last reconciled:** 2026-08-26
- **Spec ID:** TR-POOL-SMOKE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-26: Reconfirmed observational Gamma 602 HIL, independent Stratum job
  reception, healthy mining, read-only API traces, cleanup, and finalized
  artifact privacy.
- 2026-08-10: Let reconfiguration preserve the current device pool username
  when no explicit device identity is supplied, while keeping the independent
  probe identity separate.
- 2026-08-10: Reconciled observational and reconfiguration modes, independent
  probe identity, stable mining criteria, and cleanup relationship.
