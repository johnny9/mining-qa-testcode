# Configuration and selection

Resolve one runner profile into deterministic devices, tests, validation cases,
and publishers without exposing resolved secrets.

- **Lifecycle:** supported
- **Owner:** test-runner maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** TR-CONFIG

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-14: Linked strict proposed orchestration-v2 pre-device validation
  without changing current direct/v1 behavior.
- 2026-08-10: Moved lab ownership to the external `mining-qa-lab` repository
  and bound orchestration metadata to contract v1.
- 2026-08-10: Reconciled TOML, CLI, environment, device, pattern, and PR
  validation selection against the current runner and tests.
