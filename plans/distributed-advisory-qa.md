# Distributed advisory QA — test runner delivery plan

Status: proposed proof of concept and migration plan

Updated: 2026-08-14

Related plans:

- [Status service](../../mining-qa-status/plans/distributed-advisory-qa.md)
- [Lab service](../../mining-qa-lab/plans/distributed-advisory-qa.md)

Durable contracts and acceptance now live in:

- [Orchestration v2](../specs/test-runner/orchestration-v2/SPEC.md)
- [Mock-device integration](../specs/test-runner/mock-device-integration/SPEC.md)
- [Lab/Testcode orchestration v2](../contracts/orchestration-v2.md)
- [Mock device v1](../contracts/mock-device-v1.md)

## Goal

Extend `mining-qa-testcode` with enough versioned correlation metadata for one
detailed child result to participate safely in a distributed gate run, while
preserving the runner's current ownership of test discovery, device lifecycle,
cleanup, detailed evidence, privacy, provenance, and child publication.

The runner does not register labs, manage subscriptions, accept central work,
schedule gates, lease shared lab resources, or aggregate global evidence.

## Agreed product decisions that affect the runner

- Every eligible subscribed lab runs the same portable suite initially.
- The public read-only gate conclusion is advisory and separate from a concrete
  runner outcome.
- A global gate run, a per-lab execution, a local run, an assignment, and an
  attempt need distinct correlation identities.
- Detailed checks retain `passed`, `failed`, `error`, and `skipped`; skipped is
  neutral and excluded from pass/fail totals.
- A published test result is sanitized before submission and is safe to expose
  in full. Its source identity is public: project/repository and revision,
  pull request, trigger, gate/suite revision, exact testcode repository and
  commit, publisher, public lab identity, non-identifying platform/model class,
  and stable opaque run correlation IDs. Private bindings, physical-device
  aliases or identities, coordinates, credentials, local paths, pool identity,
  and raw logs never enter the published result. A separate post-run sanitized
  log may be published as detailed evidence.
- Public correlation IDs are per-run values and must not encode or derive from
  a local device ID, serial number, address, pool user, or other unit identity.
- Compatible readers must ship before a new contract writer is enabled.

## Proof-of-concept outcome

A simulated runner invocation accepts the next orchestration contract,
validates the full distributed correlation chain and definition digest before
constructing any device, emits a bounded result pointer containing the same
identities, and publishes a sanitized fake child-result payload. Version 1
direct and local-lab invocations remain supported.

No real hardware adapter, firmware path, network target, runtime source
checkout, artifact upload, or external publication is exercised.

## Ownership boundary

### Testcode continues to own

- CLI selection and validation of profiles, devices, patterns, and cases.
- Exact expected runner repository/SHA verification.
- Identify, optional update, baseline capture, tests, restoration, artifact
  collection, and interface close.
- Native detailed result records, telemetry, chart markers, artifacts,
  sanitization, and source provenance.
- Post-run log sanitization, privacy scanning, and publication of the sanitized
  copy while keeping the raw capture private.
- Detailed child publication and atomic bounded result-pointer writing.

### The lab service owns

- Offer acceptance, local policy, private requirement binding, inventory,
  shared leases, runner installation, process timeout, recovery, attempt
  history, private logs, and per-lab execution completion.

### The status service owns

- Portable definition revisions, lab eligibility, global gate runs, per-lab
  execution records, coverage, advisory assessment, and cross-lab presentation.

## Versioned orchestration contract

The exact metadata, validation primitives, correlation ownership, private
pointer, required manifest, public child section, failure mapping, bounds, and
reader/writer order are normative in
[contracts/orchestration-v2.md](../contracts/orchestration-v2.md). The Lab copy
must remain byte-identical. Version 1 remains readable throughout the proof of
concept and its compatibility window.

## Detailed child-result payload

Add a bounded, sanitized `orchestration` section to the published result when
version 2 metadata is present:

- project, gate, suite, and suite revision;
- definition digest;
- central gate-run, lab, lab-execution, assignment, and attempt IDs;
- public lab label and non-identifying platform/model classification;
- exact source and testcode provenance already allowed by publishing policy.

The published `orchestration` section contains only public source provenance and
opaque correlation identity and is safe to expose in full. The private result
pointer may additionally contain `local_gate_run_id`, worker-local artifact
paths, and other fields needed only by the lab; those fields never enter the
published result. Never publish a local device name/ID, stable per-unit alias,
serial number, USB identifier/path, MAC/IP address, device hostname/URL, mDNS
name, Bitcoin or payout address, pool username/worker identity, setup/profile
ID, artifact root, local filename, credential, environment content, or raw log.
Repository, commit, pull-request, testcode, and CI URLs remain public software
provenance. Construct the published result from an allowlist and keep the
existing recursive sanitizer as defense in depth.

Any existing `target_name`, hardware metadata, check detail, telemetry label,
summary, or nested publisher field must use a non-identifying platform/model
description. It must not default to the configured local device name. The
privacy scan covers nested keys and values and fails publication when a
prohibited identifier remains; recognizable redaction markers are not valid
published values.

### Post-run log sanitization

The runner captures raw logs only in a private bounded staging location. After
the tests finish, device cleanup completes, and interfaces close, it creates a
new sanitized log artifact; the raw object is never modified in place or
uploaded through the public artifact path.

Sanitization combines exact-value removal from the invocation's private
identity set with pattern scanning. It removes device names and IDs, serial and
USB identifiers, MAC/IP addresses, device URLs/hostnames/mDNS names, Bitcoin or
payout addresses, pool usernames and worker identities, credentials, local
paths, and any matching fragments in structured or unstructured log lines.
Fixed typed placeholders are allowed in sanitized log text, but may not retain
distinguishing fragments of the original value.

Before upload, a second independent scan examines the complete sanitized bytes
and filename. Publication records the sanitizer contract version, sanitized
size, and SHA-256 digest. If sanitization or either scan fails, the runner does
not upload or link the log, reports a bounded sanitization error in the result,
and retains or deletes the raw capture only under private local retention
policy. It never publishes the raw log as a fallback. Sanitization runs on
passing, failing, error, timeout, and cleanup-failure paths when a bounded raw
capture exists.

The detailed result URL/ID is returned through the result pointer. The lab uses
that immutable link in its per-lab summary; neither the lab nor the status
service reconstructs a detailed result from private artifacts.

## Compatibility behavior

| Invocation | Expected behavior |
|---|---|
| Direct, no orchestration metadata | Current behavior unchanged |
| Legacy metadata with no version | Read as version 1 during the documented compatibility window |
| Explicit version 1 | Current validation and pointer behavior |
| Explicit version 2 | Require all version 2 correlation fields, echo the full private correlation in the pointer, and publish only the sanitized provenance contract |
| Unknown version | Fail before hardware construction |
| Mixed or malformed version 2 fields | Fail before hardware construction |

Do not make version 2 the lab writer default until released runner versions and
lab readers both accept it. Do not backport version 2 fields into version 1 with
different meanings.

## Implementation areas

- Version-aware orchestration metadata parser and immutable typed model.
- Correlation propagation in the run summary and sanitized child-result publication.
- Version-aware result-pointer writer with the existing atomic and size rules.
- An allowlist serializer for the complete public result plus a separate
  private result-pointer serializer.
- A bounded post-run log sanitizer, independent publication scan, immutable
  sanitized artifact, and raw/sanitized provenance metadata.
- Publisher tests proving links and IDs remain consistent across local output
  and remote payload construction.
- Contract fixtures shared semantically, but not imported as code, with the lab
  repository.

The actual file/module pointers should be recorded in the new and affected
feature-spec `design.md` companions after inspecting the implementation at the
start of the change.

## Delivery sequence

Each step should be independently reviewable and keep direct runner use working.

1. **Durable intent.** Implement against the indexed orchestration-v2 and
   mock-device specs plus their versioned contracts; keep affected supported
   specs synchronized.
2. **Compatible reader.** Add the typed version 2 metadata parser and fixtures;
   preserve legacy and explicit version 1 behavior and reject unknown versions.
3. **Pre-hardware validation.** Prove malformed identities, digest, source, or
   runner provenance fail before device construction and network access.
4. **Pointer writer.** Echo the immutable correlation object in a bounded atomic
   version 2 pointer while retaining the version 1 writer for version 1 input.
5. **Child payload.** Add the allowlisted public orchestration provenance,
   preserve private-only correlation in the result pointer, and add privacy
   regressions for every forbidden field.
6. **Sanitized logs.** Capture a bounded private raw log, create and scan a
   separate sanitized artifact after the run, and publish only that artifact
   with sanitizer version and digest.
7. **Mock device process.** Implement the loopback Gamma control/device API,
   simulated miner client, required fault scenarios, and structured event
   ledger from `contracts/mock-device-v1.md`.
8. **Simulated end-to-end fixture.** Produce passing, failing, and cleanup-error
   child results through the real Gamma adapter and verify distinct correlation
   chains plus final mock baselines.
9. **Writer enablement.** Only after coordinated lab reader support is released,
   allow the lab to invoke version 2. Version 1 remains available through the
   announced compatibility window.

## Proof-of-concept acceptance

- [ ] Direct invocation and legacy/version 1 fixtures retain current behavior.
- [ ] Valid version 2 metadata is accepted and all identities are immutable for
  the invocation.
- [ ] Unknown, malformed, oversized, inconsistent, or incomplete version 2
  metadata fails before any device object or transport is created.
- [ ] The version 2 pointer echoes the exact correlation chain and stays within
  existing bounded atomic-write guarantees.
- [ ] The fake published child payload contains complete non-secret source
  provenance and stable opaque correlation, with no private binding or device
  coordinate.
- [ ] The published result is safe to return unchanged and contains no local
  identity, physical-device alias, serial/USB identity, network coordinate,
  Bitcoin/payout address, pool worker identity, credential, artifact path,
  environment, or unsanitized-log field.
- [ ] Passing, failing, error, timeout, and cleanup-failure fixtures prove that
  only a distinct post-run sanitized log can be published, with sanitizer
  version and digest.
- [ ] Sanitizer or scan failure publishes no log, exposes no raw filename or
  content, and never falls back to the private raw capture.
- [ ] Passing, failing, error, and skipped outcomes retain their current
  meanings; skipped remains neutral in summaries.
- [ ] Publisher failure and cleanup failure retain current failure semantics.
- [ ] Both repository copies of the version 2 contract are semantically
  identical and tested independently.
- [ ] No hardware, firmware, external publication, or deployment is performed.

## Verification

Implementation requires focused orchestration, lifecycle, pointer, publisher,
and privacy tests, followed by:

```text
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/unit -v
PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_specs -v
python3 -m build --no-isolation
git diff --check
```

Negative cases must cover unknown version, booleans as versions, missing IDs,
oversized metadata, mismatched digest, wrong runner repository/SHA, unsafe
publisher data, pointer overflow, and cleanup failure. Passing unit simulations
are not HIL evidence.

## Later phases, not part of the proof of concept

- Contract retirement criteria and telemetry for remaining version 1 callers.
- Cross-lab comparison helpers in the presentation layer; not in the runner.
- Additional portable requirement vocabulary where real suites demonstrate a
  need.
- Real hardware qualification under explicit per-target authorization.

## Rollback rule

Version 2 support is additive. Disabling its writer path leaves direct and
version 1 invocations unchanged. A failed proof of concept removes no existing
contract, publisher, profile, test, or hardware behavior.
