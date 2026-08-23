# Mock-device integration

Exercise the real Gamma adapter, lifecycle, and Stratum path against a
deterministic loopback process so full system tests require no physical miner.

- **Lifecycle:** supported
- **Owner:** test-runner maintainers
- **Last reconciled:** 2026-08-16
- **Spec ID:** TR-MOCK

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-16: Added the loopback mock process, bounded native AxeOS/control
  endpoints, simulated Stratum client, deterministic scenarios/event ledger,
  and real Gamma adapter integration profile/test.
- 2026-08-16: Added direct component coverage for every declared failure
  scenario family, bounded fault controls, unsupported operations, loopback/
  path isolation, and private-raw/public-sanitized privacy canaries.
- 2026-08-14: Defined Testcode ownership, loopback process/control/device API,
  simulated Stratum client, fault scenarios, event ledger, and HIL boundary.
