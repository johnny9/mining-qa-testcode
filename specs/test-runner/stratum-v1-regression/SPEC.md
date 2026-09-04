# Stratum V1 regression

Exercise deterministic miner-client behavior against a controlled local
Stratum V1 server, including valid work, rejected work, and bounded failures.

- **Lifecycle:** supported
- **Owner:** hardware-test maintainers
- **Last reconciled:** 2026-09-04
- **Spec ID:** TR-STRATUM

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-04: Bound ESP-Miner job IDs, selected the newest post-restart
  connection, and completed Gamma 602 HIL for PR 1897; a broader run separately
  found that PR 1849's opt-in embedded-NUL reconnect case times out on the
  target firmware.
- 2026-08-14: Linked the proposed mock miner client that completes the
  device-to-fake-pool path for no-hardware integration.
- 2026-08-10: Defined class-scoped fake-pool lifecycle, ordered scenarios,
  protocol evidence, privacy rules, and hardware acceptance boundary.
