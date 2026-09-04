# Transport interfaces

Provide bounded, observable, and failure-aware HTTP, WebSocket, serial, and
Stratum communication without hiding uncertain writes.

- **Lifecycle:** supported
- **Owner:** interface maintainers
- **Last reconciled:** 2026-09-04
- **Spec ID:** TR-IO

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-04: Added a bounded authenticated Stratum V2 fake-server transport
  for deterministic encrypted protocol regression.
- 2026-08-10: Reconciled operation serialization, read-only enforcement,
  bounded messages/responses, safe retry rules, and serial resolution.
