# Artifacts, privacy, and provenance

Retain diagnostic evidence that is attributable to exact source and hardware
without publishing secrets, payout identities, or sensitive local coordinates.

- **Lifecycle:** supported
- **Owner:** hardware-test maintainers
- **Last reconciled:** 2026-09-04
- **Spec ID:** TR-EVIDENCE

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-04: Redacted SV2 authority public keys from saved pool-baseline
  evidence while retaining them only in memory for restoration.
- 2026-08-26: Registered configured API, WebSocket, and serial coordinates as
  run-scoped private replacements and added fail-closed `.local` hostname
  redaction after a representative Gamma HIL artifact audit found a leak.
- 2026-08-16: Implemented the v2 public/private correlation split, private raw
  runner/device logs, and independently scanned digest-addressed sanitized-log
  publication with mock-device privacy canaries.
- 2026-08-10: Added a bounded hash manifest of finalized sanitized artifacts for
  private lab archival redundancy.
- 2026-08-10: Reconciled external `mining-qa-lab` source expectations with the
  versioned cross-repository contract.
- 2026-08-10: Added pre-hardware verification of orchestrated expected testcode
  repository and SHA.
- 2026-08-10: Consolidated artifact layout, privacy transformations, stable
  device labels, HTTP trace policy, and source-provenance constraints.
