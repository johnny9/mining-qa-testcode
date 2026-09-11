# Stratum V2 regression

Exercise deterministic ESP-Miner client behavior against a controlled local
Stratum V2 server over an authenticated Noise session.

- **Lifecycle:** supported
- **Owner:** hardware-test maintainers
- **Last reconciled:** 2026-09-11
- **Spec ID:** TR-STRATUM-V2

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-11: Reused the authenticated server in the separate pool-fallback
  module for both channel modes, complete silence, and endpoint recovery.
  The original ordered protocol suite remains unchanged.
- 2026-09-04: Completed authorized Gamma 602 HIL with all seven ordered cases
  passing, verified independent post-cleanup mining, and taught restart
  readiness to read SV2 authentication from the primary pool when its flat API
  alias is absent.
- 2026-09-04: Implemented and unit-tested the authenticated fake server,
  ordered regression suite, catalog/config surfaces, sanitized evidence, and
  complete SV2 pool-setting cleanup; physical-miner HIL remains pending.
- 2026-09-04: Defined the local encrypted SV2 server, ordered standard or
  extended-channel scenarios, protocol-aware device configuration, evidence,
  bounds, and cleanup contract.
