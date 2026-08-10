---
name: specs
description: Create, update, reconcile, and review durable mining-qa-testcode specifications under specs/. Use for new features; observable behavior changes; APIs, protocols, files, payloads, schemas, migrations, hardware interfaces, or architectural changes; security-, safety-, performance-, resource-, recovery-, or compatibility-relevant work; implementation from an existing spec; PRs missing documentation; project overview or story-map refreshes; and product or architecture reviews.
---

# Project specifications

Maintain durable intent without duplicating implementation. Use `AGENTS.md` and
the repository README to discover verification commands. Never assume a local
device, secret, service, network, ignored profile, or HIL authorization.

## Core contract

1. Read `AGENTS.md`, `specs/README.md`, and `specs/INDEX.md`.
2. Locate the relevant feature and read every companion file, especially
   acceptance and risks.
3. Read directly related feature specs named in `design.md`.
4. Treat specs as intent and current code, tests, measurements, and live checks
   as implementation evidence.
5. Report contradictions instead of silently choosing one source.
6. Update specs and implementation together when the requested work includes
   both.
7. Keep `SPEC.md` canonical and `INDEX.md` complete.

Do not turn specs into class catalogs or line-by-line implementation tours.
Include symbols, paths, protocols, commands, hardware components, or external
systems only when they clarify a durable contract, constraint, ownership
boundary, risk, or verification method.

Preserve the repository boundary: `miner-test` owns detailed child execution
and publication; external `mining-qa-lab` owns authorized gate aggregation and
child links. Coordinate changes to `contracts/orchestration-v1.md` with the lab.
Never transfer private lab control to Mining QA Status.

## Select the workflow

### New feature or significant change

1. Search `specs/INDEX.md` and the tree for an existing feature.
2. Choose a stable area and feature slug based on the domain, not the source
   directory.
3. Copy `specs/_template/` to `specs/<area>/<feature>/`.
4. Complete `SPEC.md`, `intent.md`, and `acceptance.md` before implementation.
5. Add exactly one row to `specs/INDEX.md` in the same change.
6. Complete `design.md` and `risks.md` to the degree needed by the change.
7. Update `OVERVIEW.md` or `STORY-MAP.md` if a project-level capability, actor,
   or ownership flow changes.
8. Implement against the acceptance criteria.
9. Reconcile the feature using current evidence.

### Existing feature change

1. Read the complete feature spec and direct relationships.
2. Determine whether the change affects observable behavior, an interface, a
   documented constraint, operations, compatibility, hardware safety,
   security, privacy, performance, resources, or recovery.
3. Establish current evidence and reproduce defects before mutation when
   practical.
4. Make the implementation change using repository verification.
5. Update affected acceptance, design, intent, or risk content.
6. Reconcile lifecycle, evidence, last-reconciled date, and changelog.

Do not require a spec update for formatting, dependency-only work, test-only
cleanup, internal renames, or behavior-preserving refactors unless they change
something the specs promise or constrain.

### Implement from a spec

1. Read the feature entry and all companions.
2. Compare every acceptance criterion and durable design requirement with
   implementation evidence.
3. Classify gaps as missing implementation, stale documentation, ambiguity, or
   missing verification.
4. Resolve in-scope gaps.
5. Run repository-defined verification.
6. Reconcile the spec and report unresolved gaps precisely.

### Reconcile a feature

1. Compare intent and acceptance with current behavior.
2. Verify design pointers, interfaces, state ownership, failure behavior,
   compatibility, safety, and resource constraints.
3. Check acceptance boxes only when current evidence supports them.
4. Record concise evidence in `acceptance.md`, distinguishing unit, package,
   service, protocol, simulation, and HIL checks.
5. Update `Lifecycle` and `Last reconciled` in `SPEC.md`.
6. Append a dated changelog entry explaining the material change.
7. Confirm the index row and high-level links use the canonical path.
8. Run `specs/MAINTENANCE.md` and the spec integrity unit test.

## Feature content rules

### `SPEC.md`

Keep:

- A clear title and one-line summary.
- A stable feature ID.
- `Lifecycle`: `proposed`, `implementing`, `supported`, `deprecated`, or
  `retired`.
- Owner or responsible role when known.
- `Last reconciled`: the date of the latest code/evidence comparison, or
  `never`.
- Links to every existing companion file.
- A dated changelog.

### `intent.md`

Describe the problem, why it matters, stakeholders, desired outcome, primary
and failure flows, and explicit non-goals. Stakeholders may be developers,
reviewers, lab operators, services, devices, firmware, pools, or dependent
systems.

### `acceptance.md`

Use stable IDs and independently verifiable statements. Cover applicable
functional behavior, interfaces, compatibility, failure behavior, privacy,
authorization, hardware safety, operations, and resource limits. Record
evidence such as tests, static checks, package builds, protocol traces,
deployment checks, live service checks, or HIL.

Use `[x]` only for criteria verified during the latest reconciliation. Do not
infer completion from implementation names or stale historical results. Label
historical hardware evidence and keep criteria unchecked when current evidence
is unavailable.

### `design.md`

Capture stable responsibilities and implementation pointers plus every
applicable surface:

- CLI arguments and exit status
- TOML/YAML configuration
- environment variables and secret boundary
- Python API and extension points
- HTTP and external protocols
- files, artifacts, result payloads, and persistent state

Also document required and forbidden behavior, control/data flow, failure and
recovery, compatibility, resource constraints, related feature slices, and
verification strategy. Use `none` explicitly for non-applicable interfaces.

### `risks.md`

Capture in/out scope, assumptions, open questions, failure modes, rollout and
rollback, and applicable security, privacy, safety, timing, memory, storage,
power, capacity, image-size, network, or hardware risks.

## Supported requests

- **`create feature spec`** — create from `_template`, complete initial intent
  and acceptance, and register exactly once in the index.
- **`implement from spec`** — identify and close implementation or
  documentation gaps.
- **`sync feature`** — reconcile one feature with current evidence.
- **`refresh overview`** — update `OVERVIEW.md`, keep it concise, and append its
  changelog.
- **`update story map`** — refresh outcome navigation without replacing the
  complete index.
- **`add flow diagram`** — add Mermaid only when it makes a relationship or
  state transition materially clearer.
- **`prepare for review`** — run readiness and maintenance checks and report
  exact pass/fail gaps.
- **`start review`** or **`review`** — run the inline review workflow.
- **`apply review`** — apply a confirmed, feature-matched review to specs and
  implementation.

## Prepare for review

Classify the change:

- **Trivial:** formatting, comments, dependency-only, test-only, internal
  rename, or other work with no documented impact.
- **Spec-worthy:** new or changed behavior, interface, schema, protocol, file
  format, migration, architecture, operation, compatibility, security,
  privacy, hardware safety, recovery, resource, or performance constraint.

For spec-worthy work, require:

- Relevant feature-spec changes.
- A current changelog entry.
- Updated acceptance, design, or risk content when affected.
- A new index entry for a new feature.
- Relevant current verification evidence.
- No unresolved navigation, placeholder, or duplication failures from
  `specs/MAINTENANCE.md` and `tests.unit.test_specs`.

Report this check as advisory unless repository policy or the user makes it
blocking.

## Inline review workflow

### Select review type

- Use **Product** for intent, stakeholder value, outcomes, acceptance, scope,
  or prioritization.
- Use **Architecture** for interfaces, state/data, components, migrations,
  dependencies, ownership, security, privacy, hardware safety, recovery,
  performance, or resources.
- If both are substantial, run Product first and offer Architecture afterward.
- Follow an explicitly requested type.

### Collect context

1. Establish the requested diff scope: uncommitted changes, a commit, a branch
   comparison, or another explicit set.
2. Read changed feature specs and contextual relationships.
3. Read implementation and verification from the same scope.
4. Search `specs/reviews/` for prior reviews matching the feature slug.
5. Read earlier changelog decisions and risks.

Stop and ask whether to continue when the change is genuinely trivial.

### Challenge one dominant risk

Choose one evidence-backed risk rather than a generic list.

Product frames include intent drift, weak problem, scope creep, missing success
criteria, contradiction, premature commitment, and escalating user or
operational risk.

Architecture frames include interface design, state ownership, dependency and
system boundaries, security, privacy, hardware safety, recovery, scalability,
timing, resource use, compatibility, and maintainability.

Present:

1. Feature status.
2. Risk frame.
3. A specific claim.
4. A yes/no critical question.
5. Two to four discussion steps.
6. Concrete spec, code, test, measurement, or operational evidence.

Walk through one discussion step per message. If the user rejects the framing,
reread evidence and choose a different frame.

### Save the review

1. Synthesize decision, rationale, exact spec updates, open questions, and
   actions.
2. Ask the user to confirm before saving.
3. Copy `specs/reviews/TEMPLATE.md` to
   `specs/reviews/YYYY-MM-DD-<product|architecture>-<feature-slug>-review.md`.
4. Mark status accepted only when confirmed.
5. Append the feature changelog.
6. Ask separately whether to apply accepted updates now.

### Apply a review

1. Identify the requested feature first.
2. Filter `specs/reviews/` by that feature slug.
3. Select the requested review or latest accepted matching review.
4. Apply confirmed spec changes.
5. Treat updated specs as intent and close in-scope implementation gaps.
6. Verify and report changes, evidence, and remaining questions.

Never select a review merely because it is the newest globally.

## Project-specific reconciliation cautions

- Do not convert historical HIL memories or artifacts into current checked
  acceptance evidence without rerunning or clearly labeling their date and
  source.
- Do not run HIL, change a device, deploy firmware, publish a result, restart a
  service, or call external write APIs unless authorized by the request.
- When a device-write feature changes, require negative tests for read-only and
  invalid/redacted input plus cleanup evidence.
- When event trust changes, test source baselining, deduplication, contributor
  rules, exact-SHA approval, and queued-versus-running supersession.
- When parent publication changes, preserve detailed child publication and
  artifact ownership in `miner-test`.

## Finish

Before reporting completion:

1. Run applicable verification from `AGENTS.md` or `README.md`.
2. Run the automated spec integrity test and `specs/MAINTENANCE.md`.
3. Confirm no template placeholder remains in created feature files.
4. Confirm new features are indexed exactly once.
5. Confirm changelog and reconciliation metadata are current.
6. Report unverified acceptance criteria and unresolved conflicts explicitly.
