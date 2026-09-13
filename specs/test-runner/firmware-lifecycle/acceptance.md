# Firmware lifecycle — acceptance

## Functional behavior

- [x] **TR-FW-AC-01:** Disabled or already-matching firmware causes no upload.
- [x] **TR-FW-AC-02:** Missing artifacts, unsupported methods, invalid roles,
  and missing expected version fail before hardware write.
- [x] **TR-FW-AC-03:** OTA installs web before application and verifies returned
  device identity/version; USB uses shell-free configured argv.
- [x] **TR-FW-AC-04:** Firmware remains the run baseline while mutable settings
  are restored separately.

## Interfaces and compatibility

- [x] **TR-FW-AC-05:** Gamma accepts application/web lifecycle without a bridge
  artifact.
- [x] **TR-FW-AC-06:** Upgrade evidence records bounded metadata and hashes, not
  firmware contents or secret coordinates.

## Quality attributes

- [x] **TR-FW-AC-07:** Upload size, pace, timeout, and post-reboot wait are
  bounded; uncertain writes are not blindly retried.
- [ ] **TR-FW-AC-08:** Current authorized HIL proves upload order, reboot,
  expected version, application health, and operator recovery path for changed
  hardware/methods.

## Verification evidence

- 2026-09-13: `tests.unit.test_bonanza_lifecycle.RestartReadinessTest` proves
  that staged startup is awaited without an early resume, and post-reboot
  safety faults fail before a resume write.

- Source/config reconciliation and full unit suite cover method guards and
  transport write rules; reconciled 2026-08-10.
- No firmware HIL was run for this documentation iteration.

## Acceptance rule

Firmware changes are acceptable only with immutable artifact provenance,
pre-write validation, bounded one-shot writes, post-reboot identity/version
proof, explicit HIL status, and a known operator rollback path.
