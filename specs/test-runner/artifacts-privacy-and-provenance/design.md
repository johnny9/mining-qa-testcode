# Artifacts, privacy, and provenance — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Run/test artifacts | Create bounded paths and structured files | `src/miner_testcode/artifacts.py` |
| Privacy formatter | Redact secrets and map sensitive values to stable labels | `src/miner_testcode/redaction.py:PrivacyFormatter` |
| Provenance collector | Resolve repository origin, revision, cleanliness, and runtime metadata | `src/miner_testcode/provenance.py` |
| Transport tracing | Emit sanitized method/status/timing metadata | `src/miner_testcode/interfaces/api.py` |
| Runner | Finalize artifact manifest and publication inputs | `src/miner_testcode/runner.py` |

## Interfaces and contracts

### CLI

- `--artifacts-dir` selects the bounded output root; normal selection/profile
  metadata is recorded without copying secret environment values.

### Configuration

- Reporting/privacy settings define stable labels and publication behavior.
  Secret values are references, not serialized configuration output.

### Environment

- Values obtained through configured secret environment variables are
  registered for redaction and never copied into provenance.
- Orchestration metadata may contain an expected testcode repository/ref/SHA;
  the repository and SHA are execution constraints, not trusted observations.

### Python API

- `RunArtifacts` and `TestArtifacts` allocate paths and write structured data.
- `PrivacyFormatter` redacts known secrets and sanitizes nested payloads.

### HTTP or external protocols

- HTTP traces record request method, sanitized target, status, elapsed time,
  and error class; request/response bodies are excluded by default.

### Files, artifacts, payloads, and persistent state

- A run contains metadata, per-test evidence, logs, results, and publisher
  records. Paths are relative to the run root and names are sanitized.
- After publishers finish, an orchestration manifest lists each finalized file
  by safe relative path, byte size, SHA-256, and media type. Its own descriptor
  enters the result pointer.

## Contract constraints

### Required invariants

- Published device labels are stable configured aliases, not IP addresses or
  serial device paths.
- Known secrets and payout identities are redacted recursively in strings and
  structured payloads before persistence/publication.
- Provenance distinguishes origin URL, exact HEAD SHA, working-tree state, and
  externally supplied commit claims.
- When orchestration supplies expected testcode repository/SHA, independently
  resolved source must match both before artifact allocation or device creation.
- Artifact paths cannot escape the configured run root.
- The orchestration manifest excludes itself, rejects symlinks/escapes, and is
  capped at 256 KiB, 512 entries, 50 MiB per file, and 512 MiB total.

### Forbidden behavior

- Do not publish raw passwords, authorization headers, payout identities,
  device IPs, serial paths, or HTTP bodies.
- Do not claim a clean exact-source run when the working tree is dirty or the
  checked-out SHA conflicts with orchestration metadata.
- Do not overwrite an earlier run's evidence.

## Data and state

Artifacts are append/finalize oriented within a unique run directory. Privacy
mapping is run-scoped so the same sensitive value has one consistent label.

## Control and data flow

1. Collect source/runtime metadata and verify orchestrated source constraints.
2. Register sensitive values and allocate run/per-test paths.
3. Sanitize evidence at capture boundaries.
4. Finalize publisher records and write the bounded artifact manifest.
5. Expose sanitized publication inputs and the manifest descriptor.

## Failure and recovery

- Unsafe path or serialization failure fails evidence production.
- Provenance mismatch is retained explicitly and blocks strict remote claims.
- Failed publisher upload does not delete the local source artifacts.

## Compatibility and migration

Artifact schemas and stable labels are consumer contracts. Add fields
compatibly, version breaking layouts, and retain readers during migrations.

## Resource and operational constraints

Artifact sizes, traces, and telemetry are bounded. High-volume streams should
sample or roll up rather than grow without limit.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Result model and publishing](../result-model-and-publishing/SPEC.md) | Publishes only sanitized evidence and provenance. |
| [State, telemetry, and charting](../state-telemetry-and-charting/SPEC.md) | Produces structured evidence requiring bounds and privacy. |
| [Transport interfaces](../transport-interfaces/SPEC.md) | Emits privacy-safe traces. |
| [Orchestration contract v1](../../../contracts/orchestration-v1.md) | Defines expected source/run metadata and the result pointer. |
| [Lab assignment execution](https://github.com/johnny9/mining-qa-lab/blob/main/specs/lab-orchestrator/assignment-execution/SPEC.md) | Supplies expected metadata and consumes the result pointer. |
| [Lab testcode bootstrap](https://github.com/johnny9/mining-qa-lab/blob/main/specs/lab-orchestrator/testcode-bootstrap/SPEC.md) | Supplies exact expected testcode repository/SHA for independent verification. |
| [Orchestration v2](../orchestration-v2/SPEC.md) | Adds an allowlisted public correlation section and keeps private pointer identity separate. |
| [Mock-device integration](../mock-device-integration/SPEC.md) | Supplies synthetic canaries and distinct raw/sanitized log failure paths. |

## Verification approach

Unit-test recursive redaction, stable labeling, safe paths, trace exclusions,
and pre-hardware provenance mismatch behavior. Inspect representative finalized
artifacts before accepting a schema or publication change.
