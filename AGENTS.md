# Agent instructions

## Project mission

`mining-qa-testcode` owns `miner-test`: repeatable, failure-safe mining-hardware
tests, detailed evidence, privacy, provenance, and child-result publication.

The related [`mining-qa-lab`](https://github.com/johnny9/mining-qa-lab)
repository schedules authorized work and consumes only the versioned process
contracts in [contracts/orchestration-v1.md](contracts/orchestration-v1.md) and
[contracts/orchestration-v2.md](contracts/orchestration-v2.md).
Testcode must not acquire lab scheduling, durable lease, aggregate gate, or
orchestrator deployment responsibilities.

Read [specs/OVERVIEW.md](specs/OVERVIEW.md) for the ownership boundary and
[specs/INDEX.md](specs/INDEX.md) for feature-level contracts.

## Working behavior

- State material assumptions before changing public behavior, compatibility,
  hardware safety, security, privacy, or interfaces.
- Preserve unrelated work and prefer the smallest coherent change.
- Establish evidence before defect fixes and add a regression when practical.
- Keep a short verification step for multi-part work.
- Never claim tests, builds, deployments, publication, or HIL that were not run.

## Documentation contract

For non-trivial work:

1. Find the feature through `specs/INDEX.md`.
2. Read its `SPEC.md` and all companions.
3. Read directly related feature specs named in `design.md`.
4. Treat specs as intent and code/tests/measurements as evidence.
5. Update affected specs with observable behavior, interface, safety, recovery,
   compatibility, or operational changes.

Use `.agents/skills/specs/SKILL.md` for feature creation, reconciliation, and
review preparation. Cross-repository contract changes require coordinated
updates in `mining-qa-lab`; do not silently change only one consumer.

## Source-of-truth order

- `README.md`: short project introduction and quick start.
- `docs/*.md`: plain-language user manuals. Keep internal behavior, safety
  contracts, and agent instructions in specs or this file.
- `contracts/`: external lab/runner protocol versions.
- `specs/OVERVIEW.md`: purpose and ownership boundary.
- `specs/INDEX.md`: complete test-runner feature directory.
- Feature `SPEC.md` and companions: durable contracts and acceptance.
- Code and tests: current implementation evidence.

If these conflict, stop and reconcile them in the same change when in scope.

## Non-negotiable boundaries

- `miner-test` owns discovery, device lifecycle, mutable-state cleanup,
  detailed artifacts, privacy, provenance, and child-result publication.
- The runner accepts orchestration only through the documented CLI,
  environment metadata, and result-pointer file.
- The runner never publishes aggregate parent-gate status.
- Mining QA Status does not receive device credentials or control hardware.
- Devices execute on the host that owns their USB and private coordinates.

## Hardware, security, and privacy safety

- Hardware writes require explicit non-read-only configuration and a captured
  cleanup baseline.
- Cleanup failure is a test error and never hidden by a passing body.
- Never write redaction markers, masked passwords, unresolved placeholders, or
  artifact-derived values to a device.
- Preserve rollback paths and verify restored pool, pause, and mutable state.
- Secrets come through named environment variables and are never serialized.
- Bound network responses, serial input, uploads, artifacts, and metadata.
- Safe reads may retry as specified; writes do not retry without proven
  idempotence.
- Firmware changes require immutable artifacts, bounded transfer, target
  identity verification, reboot verification, and a rollback plan.
- Orchestrated expected repository/SHA mismatches fail before hardware creation.

## Project commands

Use the repository virtual environment when present.

| Purpose | Command |
|---|---|
| Install runner | `.venv/bin/python -m pip install -e .` |
| Full unit tests | `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v` |
| One unit module | `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.<module> -v` |
| Build wheel and sdist | `python3 -m build --no-isolation` |
| Run hardware tests | `.venv/bin/miner-test --config <local-toml>` |
| Documentation integrity | `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_specs -v` |
| Whitespace validation | `git diff --check` |

Hardware commands require a user-authorized target and ignored local profile.
Before HIL, re-check identity, firmware source, pool, serial path, read-only
state, and publication destination. After HIL, verify cleanup separately.

## Verification expectations

| Change | Minimum evidence |
|---|---|
| Runner/config/selection | Focused tests, full unit suite, package build |
| Device lifecycle/write path | Fake regression, negative safety case, cleanup assertion, full suite |
| Interface/protocol | Boundary and malformed-input tests, bounded behavior, full suite |
| Privacy/provenance/publishing | Redaction/provenance tests, payload assertions, full suite |
| Orchestration contract | Legacy/current/unsupported-version tests and coordinated lab update |
| Documentation only | Spec integrity, maintenance checklist, `git diff --check` |

## Repository hygiene

- Never commit local profiles, tokens, device coordinates, artifacts, firmware
  caches, service state, or generated package output.
- Stage only named task files and preserve unrelated changes.
- Commit and push only when explicitly authorized; verify the remote SHA.
- Keep code, tests, examples, contracts, and specs synchronized.

## Definition of done

- Requested behavior is complete and boundaries remain intact.
- Relevant verification passed or limitations are stated precisely.
- Public behavior matches the feature specs and versioned contract.
- Acceptance evidence, lifecycle, and changelog are current.
- New specs are indexed once and maintenance checks pass.
