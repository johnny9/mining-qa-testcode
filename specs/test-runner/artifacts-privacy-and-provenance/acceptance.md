# Artifacts, privacy, and provenance — acceptance

## Functional behavior

- [x] **TR-EVIDENCE-AC-01:** Every run and test receives a unique bounded
  artifact scope with structured metadata and results.
- [x] **TR-EVIDENCE-AC-02:** Recursive privacy formatting redacts configured
  secrets and private identity from strings and nested payloads.
- [x] **TR-EVIDENCE-AC-03:** Device addresses and serial paths are represented
  by stable configured labels in publication data.
- [x] **TR-EVIDENCE-AC-04:** Provenance records exact repository origin, HEAD,
  working-tree state, and supplied orchestration claims distinctly.
- [x] **TR-EVIDENCE-AC-09:** An orchestrated expected testcode repository or
  SHA mismatch is rejected before artifact allocation and device construction.

## Interfaces and compatibility

- [x] **TR-EVIDENCE-AC-05:** HTTP traces exclude bodies and authorization data.
- [x] **TR-EVIDENCE-AC-06:** Artifact paths cannot traverse outside the run
  root and existing runs are not overwritten.
- [x] **TR-EVIDENCE-AC-10:** Orchestrated runs emit a bounded manifest containing
  only safe finalized artifact paths with exact sizes and SHA-256 values for
  independent private archival verification.

## Quality attributes

- [x] **TR-EVIDENCE-AC-07:** Unit tests use canary secrets/identities and prove
  they are absent from serialized output.
- [ ] **TR-EVIDENCE-AC-08:** A current representative run has been manually
  audited across every local and remote artifact for privacy and provenance.

## Verification evidence

- `tests.unit.test_redaction`, `tests.unit.test_provenance`,
  `tests.unit.test_runner`, `tests.unit.test_config`, and API-interface tests
  cover the core transformations, pre-hardware source guard, and artifact
  handling and orchestration manifest hashing; reconciled 2026-08-10.
- A fresh full publication audit was not performed for this documentation
  iteration.

## Acceptance rule

Any change that adds evidence or a publisher payload needs a canary-secret
regression and schema/path test. A new remote surface is not acceptable until a
representative finalized payload is manually inspected.
