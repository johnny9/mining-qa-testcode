# Result model and publishing — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Result model | Represent tests, run outcome, evidence, and publishers | `src/miner_testcode/results.py` |
| Unittest bridge | Capture native outcomes without bypassing cleanup | `src/miner_testcode/runner.py` |
| Publisher manager | Execute configured publishers and enforce failure policy | `src/miner_testcode/publishers.py:PublisherManager` |
| Local publisher | Write canonical JSON and human-readable HTML | `src/miner_testcode/publishers.py:LocalHtmlPublisher` |
| GitHub publisher | Update the configured detailed child check | `src/miner_testcode/publishers.py:GithubCheckPublisher` |
| QA publisher | Create/finalize child run and upload authorized evidence | `src/miner_testcode/publishers.py:MiningQaStatusPublisher` |

## Interfaces and contracts

### CLI

- Normal `miner-test` exit status reflects tests, cleanup, and required
  publisher outcomes. Publisher configuration comes from the selected profile.

### Configuration

- Publisher entries define kind, enablement, required status, endpoint/repo,
  authentication environment references, and artifact policy.

### Environment

- `MINER_TEST_EXTERNAL_RUN_ID` supplies orchestrator correlation.
- `MINER_TEST_RESULT_POINTER` requests a bounded JSON pointer at that exact
  local path.
- `MINER_TEST_ORCHESTRATION_METADATA`, optional `MINER_TEST_PR_NUMBER`, and
  GitHub repository/SHA/ref variables contribute provenance, not authority to
  publish a parent gate.

### Python API

- `RunSummary`, `TestRecord`, and `PublisherRecord` form the serialized result.
- Publishers return explicit records rather than mutating test outcomes.

### HTTP or external protocols

- GitHub Checks and Mining QA Status requests are bounded and authenticated.
- Any server-issued direct upload is restricted to the supplied method, URL,
  headers, size, and artifact.

### Files, artifacts, payloads, and persistent state

- Local JSON is the canonical complete run record; HTML is a view.
- The result pointer contains only bounded correlation, status, child URL,
  and local-result location needed by the lab. Its top-level
  `contract_version` is `1`.

## Contract constraints

### Required invariants

- Native unittest success, failure, error, skip, and infrastructure/cleanup
  outcomes are preserved in the normalized model.
- Local results are produced even if remote publishers are unavailable.
- Required and best-effort publisher failures have distinct exit semantics.
- Runner publications are detailed child results; only the orchestrator owns
  aggregate gate status.
- Pointer writes are atomic and bounded.

### Forbidden behavior

- Do not let a successful upload erase a test or cleanup failure.
- Do not include unsanitized artifacts or credentials in publisher payloads.
- Do not upload to arbitrary redirects/targets outside the server-issued
  direct-upload contract.
- Do not make the child runner publish the parent gate.

## Data and state

The summary is finalized from test and cleanup records, then augmented with
publisher records without changing the underlying test truth.

## Control and data flow

1. Capture test/cleanup events and finalize the run summary.
2. Persist canonical local JSON and HTML.
3. Invoke remote publishers and append their records.
4. Re-finalize local publication metadata and atomically write the pointer.

## Failure and recovery

- Remote timeout/error is recorded; retry behavior stays bounded.
- Required publisher failure changes runner exit status.
- Pointer failure is infrastructure failure for orchestrated execution because
  the parent cannot safely correlate the child.

## Compatibility and migration

JSON/pointer fields consumed outside the runner are versioned contracts. Add
fields compatibly and coordinate breaking changes with orchestrator readers.

## Resource and operational constraints

Publisher retries, payload size, annotation count, and uploads are bounded.
Large evidence uses authorized artifact upload rather than inline payloads.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Artifacts, privacy, and provenance](../artifacts-privacy-and-provenance/SPEC.md) | Supplies safe evidence and exact source identity. |
| [Orchestration contract v1](../../../contracts/orchestration-v1.md) | Defines correlation variables and the pointer consumed externally. |
| [Lab assignment execution](https://github.com/johnny9/mining-qa-lab/blob/main/specs/lab-orchestrator/assignment-execution/SPEC.md) | Supplies correlation variables and consumes the pointer. |
| [Parent gate publication](https://github.com/johnny9/mining-qa-lab/blob/main/specs/lab-orchestrator/parent-gate-publication/SPEC.md) | Aggregates child status/link without duplicating artifacts. |
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Cleanup failures remain part of authoritative outcome. |

## Verification approach

Unit-test event aggregation, JSON schemas, every publisher's requests and
failure modes, direct-upload constraints, exit codes, and pointer atomicity.
