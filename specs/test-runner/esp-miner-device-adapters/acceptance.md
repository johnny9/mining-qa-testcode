# ESP-Miner device adapters — acceptance

## Functional behavior

- [x] **TR-BITAXE-AC-01:** Bonanza accepts only board 1002/BZM and Gamma accepts
  only board 602/BM1370.
- [x] **TR-BITAXE-AC-02:** Shared AxeOS behavior provides API, pool, state,
  telemetry, OTA, serial, logs, restart, and cleanup capabilities only when
  configured.
- [x] **TR-BITAXE-AC-03:** Legacy and multi-pool schemas configure and restore
  equivalent SV1/SV2 pool, protocol, channel, authority, and authentication
  values without writing masked credentials or redaction markers.
- [x] **TR-BITAXE-AC-04:** Gamma normalizes portable mining state without
  Bonanza-only lifecycle fields.

## Interfaces and compatibility

- [x] **TR-BITAXE-AC-05:** `bitaxe_602` remains registered and
  `Bitaxe602Device` remains a compatibility alias.
- [x] **TR-BITAXE-AC-06:** Gamma firmware configuration does not require or
  accept a separate bridge lifecycle.

## Quality attributes

- [x] **TR-BITAXE-AC-07:** Optional telemetry outages fall back to REST and
  required telemetry fails explicitly.
- [ ] **TR-BITAXE-AC-08:** Current authorized HIL confirms identity, serial,
  telemetry, mutable restore, and healthy mining for each changed model.

- [x] **TR-BITAXE-AC-09:** Omitted or explicitly disabled serial permits a
  network-only lifecycle without serial construction or USB capabilities;
  legacy serial tables remain enabled and USB upgrades fail while disabled.

## Verification evidence

- `tests.unit.test_network_only` — disabled/omitted serial lifecycle, capability
  exclusion, USB upgrade rejection, legacy compatibility, and invalid option;
  reconciled 2026-09-13.

- `tests.unit.test_bitaxe_state` — identity, inheritance, WebSocket diffs, and
  normalized state; reconciled 2026-08-10.
- `tests.unit.test_bonanza_lifecycle` — pool protocol validation plus flat and
  multi-pool SV2 configuration/cleanup contracts, delayed reboot detection,
  and primary-pool alias fallback; reconciled 2026-09-04.
- Authorized Gamma 602/BM1370 HIL on 2026-09-04 confirmed exact identity,
  serial capture, REST telemetry fallback, SV1/SV2 pool mutation, restoration,
  and healthy mining on PR 1897 firmware `1c44a87`. AC-08 remains unchecked
  because Bonanza 1002 was not exercised.

## Acceptance rule

Adapter changes are acceptable only with native fixture coverage, exact identity
rejection, capability review, cleanup proof, and an explicit statement of HIL
status.
