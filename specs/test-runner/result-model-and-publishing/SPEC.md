# Result model and publishing

Aggregate native unittest outcomes into a stable run result and publish local
or remote child records with explicit required-versus-best-effort semantics.

- **Lifecycle:** supported
- **Owner:** hardware-test maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** TR-RESULTS

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Added the optional contract-v1 artifact-manifest descriptor while
  retaining required Mining QA child publication semantics.
- 2026-08-10: Versioned the external lab process/result-pointer contract as v1
  and added atomic pointer replacement and compatibility checks.
- 2026-08-10: Defined result aggregation, publisher failure policy, direct
  upload handling, and the child-result pointer contract with orchestration.
