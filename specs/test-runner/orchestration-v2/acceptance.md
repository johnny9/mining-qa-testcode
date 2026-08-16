# Orchestration v2 — acceptance

## Functional behavior

- [x] **TR-ORCH-V2-AC-01:** Valid complete v2 metadata and matching environment/
  checkout are accepted and frozen before artifact allocation or device/network
  construction.
- [x] **TR-ORCH-V2-AC-02:** Unknown, boolean, incomplete, mixed, malformed,
  oversized, mismatched, dirty, or wrong-source v2 input fails before those
  boundaries.
- [x] **TR-ORCH-V2-AC-03:** The atomic bounded v2 pointer echoes the exact
  central gate, Lab, Lab execution, local run, assignment, attempt, and digest
  correlation and includes a required verified artifact manifest.
- [x] **TR-ORCH-V2-AC-04:** Detailed child publication contains the exact
  allowlisted public orchestration section and immutable child identity/link.
- [ ] **TR-ORCH-V2-AC-05:** Pass, fail, error, skip, cleanup failure, publisher
  failure, pointer failure, and manifest failure retain existing truth and exit
  semantics.

## Interfaces and compatibility

- [x] **TR-ORCH-V2-AC-06:** Lab and Testcode independently test byte-identical
  `contracts/orchestration-v2.md` copies.
- [x] **TR-ORCH-V2-AC-07:** Direct, legacy-v1, and explicit-v1 invocations remain
  compatible while v2 is added; Lab readers ship before its v2 writer.
- [x] **TR-ORCH-V2-AC-08:** Public child correlation is accepted by Status only
  when it matches frozen gate/Lab execution data; Testcode cannot create or
  retarget a global run.

## Quality attributes

- [x] **TR-ORCH-V2-AC-09:** Canary tests prove no private local run, device/
  setup/profile identity, coordinate, path, credential, pool/payout identity,
  environment content, or raw log enters a public payload.
- [ ] **TR-ORCH-V2-AC-10:** Post-run sanitized log publication is distinct,
  bounded, digest-addressed, independently scanned, and never falls back to raw
  capture.
- [x] **TR-ORCH-V2-AC-11:** The two-Lab local integration suite produces
  distinct complete correlation chains and exercises error/cleanup paths
  without real hardware or external publication.

## Verification evidence

- `PYTHONPATH=src python3 -m unittest discover -s tests/unit -v` passed all 70
  unit/spec tests on 2026-08-16, including strict metadata/environment,
  dirty-development opt-in, provenance, atomic pointer, manifest, publisher,
  and redaction regressions.
- The Status-owned nine-scenario development simulation published and verified
  distinct real child results for both Labs, including failed and cleanup-error
  outcomes without real hardware or external publication.
- AC-05 and AC-10 remain unchecked until the complete outcome/failure matrix
  and distinct digest-addressed sanitized-log publication have current direct
  evidence.

## Acceptance rule

Enable v2 writing only after parser/pointer/publisher/privacy tests pass, the
Lab v2 reader is released, coordinated contracts match, and full local
integration passes while v1 remains available.
