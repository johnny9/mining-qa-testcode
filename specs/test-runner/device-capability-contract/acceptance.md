# Device capability contract — acceptance

## Functional behavior

- [x] **TR-DEVICE-AC-01:** A registered type constructs the expected adapter;
  an unknown type fails with the supported type set.
- [x] **TR-DEVICE-AC-02:** Tests missing required capabilities skip before
  device startup.
- [x] **TR-DEVICE-AC-03:** Adapters expose the complete lifecycle, normalized
  state store, and telemetry contract.
- [x] **TR-DEVICE-AC-04:** Wrong board/ASIC identity fails before hardware
  mutation.

## Interfaces and compatibility

- [x] **TR-DEVICE-AC-05:** Bonanza and Gamma extend the common Bitaxe adapter
  while generic tests remain model independent.
- [x] **TR-DEVICE-AC-06:** Capability names are stable behavior contracts and
  not inferred from model strings in tests.

## Quality attributes

- [x] **TR-DEVICE-AC-07:** Native lifecycle differences map to portable
  `mining_active`, fault, pool, work-age, and telemetry meanings.

## Verification evidence

- `tests.unit.test_bonanza_lifecycle` covers SV1-default compatibility,
  invalid protocol/channel rejection, and SV2 pool settings; reconciled
  2026-09-04.
- `tests.unit.test_bitaxe_state` — inheritance, identity, lifecycle, and state
  normalization; reconciled 2026-08-10.
- Runner/testcase unit coverage in the full suite verifies pre-start selection
  and generic binding.

## Acceptance rule

A new adapter is acceptable only when it implements every abstract method,
advertises only real capabilities, rejects wrong identity, supplies normalized
state/telemetry, proves cleanup, is factory registered, and runs applicable
generic tests unchanged.
