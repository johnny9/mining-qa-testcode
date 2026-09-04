# ESP-Miner device adapters

Adapt AxeOS on Bitaxe Bonanza 1002 and Gamma 602 into the common device,
lifecycle, pool, firmware, state, and telemetry contracts.

- **Lifecycle:** supported
- **Owner:** ESP-Miner adapter maintainers
- **Last reconciled:** 2026-09-04
- **Spec ID:** TR-BITAXE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-04: Verified Gamma 602 SV1/SV2 pool mutation and cleanup in HIL,
  hardened restart detection, and supported SV2 fields present only in the
  primary pool object.
- 2026-09-04: Added native SV2 protocol/channel/authority/auth configuration,
  capability advertising, validation, and flat/multi-pool restoration.
- 2026-08-14: Linked the proposed versioned Gamma mock API used only for
  no-hardware integration through the real adapter.
- 2026-08-10: Reconciled model identity, shared adapter behavior, multi-pool
  cleanup, standard Gamma telemetry, and redacted-identity rejection.
