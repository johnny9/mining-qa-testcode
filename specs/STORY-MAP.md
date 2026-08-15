# Story map

This map navigates testcode by outcome. [INDEX.md](INDEX.md) is the complete
feature directory.

## Define and select trustworthy tests

- Select devices, patterns, and PR validation cases →
  [Configuration and selection](test-runner/configuration-and-selection/SPEC.md)
- Target normalized behavior rather than a model →
  [Device capability contract](test-runner/device-capability-contract/SPEC.md)
- Add an ESP-Miner model without forking generic tests →
  [ESP-Miner device adapters](test-runner/esp-miner-device-adapters/SPEC.md)

## Exercise hardware safely

- Restore mutable miner state after every outcome →
  [Lifecycle and cleanup](test-runner/lifecycle-and-cleanup/SPEC.md)
- Observe bounded concurrent interfaces →
  [Transport interfaces](test-runner/transport-interfaces/SPEC.md)
- Target and verify explicit firmware →
  [Firmware lifecycle](test-runner/firmware-lifecycle/SPEC.md)

## Produce protocol and mining evidence

- Observe normalized mining health and markers →
  [State, telemetry, and charting](test-runner/state-telemetry-and-charting/SPEC.md)
- Verify public-pool reachability and live mining →
  [Public pool smoke](test-runner/public-pool-smoke/SPEC.md)
- Exercise deterministic Stratum framing and work →
  [Stratum V1 regression](test-runner/stratum-v1-regression/SPEC.md)

## Preserve and publish results

- Keep evidence useful without exposing lab identities →
  [Artifacts, privacy, and provenance](test-runner/artifacts-privacy-and-provenance/SPEC.md)
- Produce a bounded hash manifest for private lab archival redundancy →
  [Artifacts, privacy, and provenance](test-runner/artifacts-privacy-and-provenance/SPEC.md)
- Publish one detailed model locally and remotely →
  [Result model and publishing](test-runner/result-model-and-publishing/SPEC.md)

## Integrate with the lab

- The external lab can invoke a pinned runner and consume a bounded pointer →
  [Orchestration contract v1](../contracts/orchestration-v1.md)
- A distributed Lab execution can preserve strict public/private correlation →
  [Orchestration v2](test-runner/orchestration-v2/SPEC.md)
- The full local stack can exercise the real adapter and lifecycle without a
  physical miner →
  [Mock-device integration](test-runner/mock-device-integration/SPEC.md)
