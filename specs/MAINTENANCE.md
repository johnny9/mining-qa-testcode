# Specification maintenance

Run this checklist when adding or reconciling features, preparing a release,
or reviewing documentation quality.

## Automated integrity

Run:

```bash
PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_specs -v
```

The check verifies canonical index coverage, unique feature paths, supported
lifecycle values, required companion files and headings, relative Markdown
links, and referenced repository paths.

## Navigation integrity

- [ ] Every `specs/**/SPEC.md` outside `_template/` is listed exactly once in
  `specs/INDEX.md`.
- [ ] Every index and companion link resolves.
- [ ] No feature exists under two canonical paths unless the duplication is
  intentional and documented.
- [ ] `OVERVIEW.md` and `STORY-MAP.md` point to canonical feature paths.
- [ ] Every public CLI command, top-level config section, endpoint family,
  device capability, publisher, persistent transition, and external protocol
  has one primary feature owner.

## Feature integrity

- [ ] `SPEC.md` has a concise summary, lifecycle, owner, last-reconciled date,
  companion links, and dated changelog.
- [ ] `intent.md` explains the problem, stakeholders, desired outcome, primary
  and failure flows, and non-goals.
- [ ] `acceptance.md` contains independently verifiable criteria with stable
  identifiers.
- [ ] Checked criteria have current evidence; historical evidence is labeled.
- [ ] `design.md` names applicable CLI, config, environment, Python, REST,
  protocol, file, payload, and state contracts.
- [ ] `design.md` records components, state ownership, control flow, failure and
  recovery, compatibility, constraints, related slices, and verification.
- [ ] `risks.md` records in/out scope, assumptions, open questions, failure
  modes, rollout/rollback, and applicable security, privacy, safety, and
  resource risks.

## Change integrity

- [ ] Observable changes update relevant specs in the same change.
- [ ] New features are indexed exactly once.
- [ ] Project-level changes update `OVERVIEW.md` or `STORY-MAP.md`.
- [ ] The changelog explains what changed and why.
- [ ] Temporary decisions that became durable moved out of `plans/`.
- [ ] Review records use the feature slug and global `specs/reviews/` path.

## Project-specific safety audit

- [ ] The cross-repository orchestration contract remains versioned and the
  testcode-child/lab-parent publication ownership remains intact.
- [ ] Device writes retain baseline, cleanup, negative, and read-only coverage.
- [ ] Secrets and private coordinates remain environment-only or ignored local
  configuration.
- [ ] Firmware deployment retains exact SHA, digest, member, board identity,
  reboot, and fail-closed evidence.
- [ ] Event trust retains baseline-first polling, trusted contributor rules,
  exact-SHA approval, and active-cleanup protection.
- [ ] Unit, build, service, protocol, and HIL evidence are reported as distinct
  verification classes.

## Tool independence

- [ ] Specs do not assume an editor or agent platform.
- [ ] Tool and runtime dependencies are feature constraints rather than
  universal assumptions.
- [ ] Verification criteria allow automated tests, analysis, protocol traces,
  package checks, live service checks, or explicitly authorized HIL as
  appropriate.
