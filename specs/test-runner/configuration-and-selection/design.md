# Configuration and selection — design

## Components and responsibilities

| Component | Responsibility | Implementation pointer |
|---|---|---|
| Config loader | Resolve TOML and exact environment references into frozen models | `src/miner_testcode/config.py` |
| Runner parser | Apply bounded device, pattern, verbosity, and PR overrides | `src/miner_testcode/runner.py:build_parser` |
| Suite loader | Bind one immutable context per selected device and filter imported cases | `src/miner_testcode/runner.py:_load_device_suite` |
| Validation decorator | Associate methods with positive PR numbers | `src/miner_testcode/testcase.py:validation_test` |

## Interfaces and contracts

### CLI

- `miner-test --config <toml>` selects the profile; `MINER_TEST_CONFIG` supplies
  the default and otherwise `config.toml` is used.
- Repeatable `--device` selects enabled configured names.
- `--pattern` overrides unittest discovery; repeatable `--validation-pr`
  unions with `runner.validation_prs`; `-v` increases verbosity.
- Exit 0 means tests and required publishers succeeded, 1 means executed work
  was unsuccessful, and 2 means configuration or local I/O was invalid.

### Configuration

- `[runner]`, `[[devices]]`, `[tests.*]`, and `[publishers.*]` are the top-level
  TOML contracts. Paths resolve relative to the profile.
- Device names are unique; at least one device exists; only enabled selected
  devices run. Interfaces and options are device-owned mappings.
- `publication_name` is the stable public label.

### Environment

- A string exactly equal to `${NAME}` resolves from the environment or fails.
  Partial interpolation is intentionally unsupported.
- Lab metadata is the separate bounded JSON environment contract in
  [orchestration contract v1](../../../contracts/orchestration-v1.md).

### Python API

- `RunnerConfig`, `DeviceConfig`, and `ProjectConfig` are frozen data contracts.
- `ProjectConfig.selected_devices()`, `test_settings()`, and
  `publisher_settings()` provide selection/access boundaries.
- `validation_test(*positive_pr_numbers)` marks opt-in test methods.

### HTTP or external protocols

- None. This slice selects later interfaces but performs no network call.

### Files, artifacts, payloads, and persistent state

- Input is one local TOML file. Resolved configuration is held in memory and is
  not serialized into run artifacts.
- `run.json` records relative profile/test paths, public devices, selection,
  runtime version, and test-code provenance without resolved settings.

## Contract constraints

### Required invariants

- Selection completes before device creation.
- Discovered E2E tests inherit `MinerTestCase` and originate under the
  configured test directory.
- PR validation cases remain discoverable and explicitly skipped when not
  selected.

### Forbidden behavior

- Do not place secrets directly in committed profiles or serialize resolved
  environment values.
- Do not silently ignore requested missing or disabled devices.
- Do not make model checks in generic tests when a capability can express the
  requirement.

## Data and state

- Configuration mappings are copied and exposed through immutable proxies.
- A `TestContext` binds the same project configuration, device configuration,
  artifact root, source root, and validation set to each case for one device.

## Control and data flow

1. Parse CLI and TOML; resolve exact environment references.
2. Validate selections and resolve provenance/publication requirements.
3. Discover, validate, bind, and execute one suite per selected device.

## Failure and recovery

- Invalid input → fail before hardware and return CLI status 2.
- No matching tests → fail rather than report an empty success.

## Compatibility and migration

- New required fields need defaults or explicit migration notes in examples and
  this spec. Existing device `options` and `interfaces` remain adapter-owned.

## Resource and operational constraints

- Orchestration metadata is limited to 64 KiB. Test selection must remain
  deterministic and must not probe hardware during configuration.

## Relationships to other feature slices

| Related feature | Relationship |
|---|---|
| [Lifecycle and cleanup](../lifecycle-and-cleanup/SPEC.md) | Selection supplies the immutable per-case context. |
| [Device capability contract](../device-capability-contract/SPEC.md) | Device type selects an adapter; capabilities select behavior. |
| [Result model and publishing](../result-model-and-publishing/SPEC.md) | Publisher tables and public labels shape output destinations. |
| [Lab assignment execution](https://github.com/johnny9/mining-qa-lab/blob/main/specs/lab-orchestrator/assignment-execution/SPEC.md) | External lab uses only contract-v1 CLI/environment overrides. |

## Verification approach

- Unit-test parsing, environment resolution, duplicates, selections, invalid PR
  values, discovery, and opt-in skip behavior without hardware.
