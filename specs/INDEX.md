# Specification index

Every testcode feature-level `SPEC.md` appears exactly once. Paths are domain
slices, not source-directory mirrors.

| Area | Feature | Lifecycle | Link | Summary |
|---|---|---|---|---|
| `test-runner` | Configuration and selection | supported | [SPEC.md](test-runner/configuration-and-selection/SPEC.md) | Resolve runner profiles, devices, tests, environment values, and opt-in validation cases. |
| `test-runner` | Lifecycle and cleanup | supported | [SPEC.md](test-runner/lifecycle-and-cleanup/SPEC.md) | Own a failure-safe device lifecycle with verified mutable-state restoration. |
| `test-runner` | Device capability contract | supported | [SPEC.md](test-runner/device-capability-contract/SPEC.md) | Let generic tests target normalized capabilities instead of miner models. |
| `test-runner` | ESP-Miner device adapters | supported | [SPEC.md](test-runner/esp-miner-device-adapters/SPEC.md) | Adapt Bonanza 1002 and Gamma 602 AxeOS behavior into common contracts. |
| `test-runner` | Transport interfaces | supported | [SPEC.md](test-runner/transport-interfaces/SPEC.md) | Bound and serialize HTTP, WebSocket, serial, and Stratum transport behavior. |
| `test-runner` | Firmware lifecycle | supported | [SPEC.md](test-runner/firmware-lifecycle/SPEC.md) | Apply explicit OTA or USB artifacts and verify target firmware identity. |
| `test-runner` | State, telemetry, and charting | supported | [SPEC.md](test-runner/state-telemetry-and-charting/SPEC.md) | Normalize mining health and retain independently observed telemetry evidence. |
| `test-runner` | Public pool smoke | supported | [SPEC.md](test-runner/public-pool-smoke/SPEC.md) | Verify pool protocol reachability and stable mining with optional device reconfiguration. |
| `test-runner` | Stratum V1 regression | supported | [SPEC.md](test-runner/stratum-v1-regression/SPEC.md) | Exercise deterministic miner-client protocol behavior against a local fake pool. |
| `test-runner` | Artifacts, privacy, and provenance | supported | [SPEC.md](test-runner/artifacts-privacy-and-provenance/SPEC.md) | Preserve useful evidence without leaking identities, secrets, or local coordinates. |
| `test-runner` | Result model and publishing | supported | [SPEC.md](test-runner/result-model-and-publishing/SPEC.md) | Aggregate native unittest outcomes and publish local or remote child results. |
| `test-runner` | Orchestration v2 | implementing | [SPEC.md](test-runner/orchestration-v2/SPEC.md) | Carry strict distributed correlation through the private pointer and sanitized child result. |
| `test-runner` | Mock-device integration | implementing | [SPEC.md](test-runner/mock-device-integration/SPEC.md) | Exercise the real Gamma lifecycle and fake Stratum path without physical hardware. |

Allowed lifecycle values: `proposed`, `implementing`, `supported`, `deprecated`,
and `retired`.
