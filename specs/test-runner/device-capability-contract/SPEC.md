# Device capability contract

Let generic tests depend on portable behavior while adapters own native miner
APIs, identity, lifecycle, and telemetry.

- **Lifecycle:** supported
- **Owner:** device-adapter maintainers
- **Last reconciled:** 2026-09-04
- **Spec ID:** TR-DEVICE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-04: Added a distinct Stratum V2 capability and additive,
  SV1-compatible pool protocol/channel/authority settings.
- 2026-08-14: Linked the proposed mock-device process that exercises the real
  Gamma adapter rather than adding a production mock adapter.
- 2026-08-10: Reconciled the abstract lifecycle, capability registry, factory,
  and normalized state extension requirements.
