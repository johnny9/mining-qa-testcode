# Module catalog — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Catalog asset | Declare reviewed module metadata and portable options | `src/miner_testcode/module-catalog.v1.json` |
| Catalog parser | Strictly validate catalog and selections and apply an immutable settings overlay | `src/miner_testcode/module_catalog.py` |
| Config loader | Merge a valid selection after ordinary private profile resolution | `src/miner_testcode/config.py` |
| Status discovery | Read the asset at an exact GitHub revision and project it into the gate editor | external `mining-qa-status` definition discovery API |

## Interfaces and contracts

### CLI

No new CLI flags. Existing selection and exit codes remain unchanged.

### Configuration

Private TOML remains authoritative for device coordinates, credentials, pool
identity, and Lab-specific defaults. A portable overlay may replace only keys
declared by the selected module. SV1 exposes `max_ntime_roll_seconds`
(0–120, default 0), `healthy_reconnect_cycles` (3–10, default 3), and
`job_burst_count` (12–64, default 24). These options do not enable PR cases.

### Environment

`MINER_TEST_MODULE_OPTIONS` is optional UTF-8 JSON, at most 16 KiB, with exact
fields `schema_version`, `module_id`, and `values`. Values are booleans,
bounded integers, or bounded strings allowed by that module's catalog. Floats
are excluded so Status and Lab compute identical portable-definition digests.

### Python API

The catalog parser returns frozen module/option records and validates one
selection. The config loader consumes only the resulting allowlisted mapping.

### HTTP or external protocols

None in Testcode. GitHub file retrieval is Status-owned.

### Files, artifacts, payloads, and persistent state

The catalog is package data and contains no secrets. The selected option map is
ephemeral and is not copied into public result payloads; the immutable central
definition digest remains its provenance.

## Contract constraints

### Required invariants

- Module and option IDs are unique opaque identifiers.
- Patterns are relative filenames without whitespace, traversal, or shell
  syntax.
- Defaults validate against their own declaration.
- Portable option keys use a conservative allowlist and never contain secret,
  credential, address, host, path, command, token, user, worker, or pool terms.
- Selection validation completes before unittest discovery or device creation.

### Forbidden behavior

- Do not import repository Python to discover metadata.
- Do not accept arbitrary JSON into `[tests.*]`.
- Do not expose or override private profile keys.

## Data and state

Catalog and selection records are immutable in memory. No durable runner state
is added.

## Control and data flow

1. Load and strictly validate packaged catalog.
2. Parse optional bounded selection JSON.
3. Resolve the selected module and validate every value.
4. Overlay values onto that module's private/default test settings.
5. Continue the existing deterministic runner flow.

## Failure and recovery

Invalid catalog or selection is a configuration error with exit status 2 and
no hardware use. Removing the environment payload restores legacy behavior.

## Compatibility and migration

The environment input is optional. Catalog schema changes require a new asset
version; v1 readers reject unknown schema versions.

## Resource and operational constraints

Catalog size is at most 256 KiB, selection size at most 16 KiB, modules at most
128, options per module at most 64, and strings are explicitly bounded.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Configuration and selection](../configuration-and-selection/SPEC.md) | Owns private profile resolution and consumes the validated overlay. |
| [Device capability contract](../device-capability-contract/SPEC.md) | Runtime adapters independently enforce actual device capabilities. |
| [Orchestration v2](../orchestration-v2/SPEC.md) | Carries the central definition digest and exact Testcode provenance. |

## Verification approach

Unit-test asset parsing, duplicate/unknown/private keys, numeric and enum
bounds, default validation, overlay behavior, and legacy no-payload behavior;
then run the full suite and build wheel/sdist contents.
