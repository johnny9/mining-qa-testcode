# Firmware lifecycle

Apply explicitly configured OTA or USB artifacts in the safe order and verify
the target firmware before testing.

- **Lifecycle:** supported
- **Owner:** device-adapter maintainers
- **Last reconciled:** 2026-08-10
- **Spec ID:** TR-FW

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-08-10: Moved whole-gate artifact selection/deployment ownership to the
  external `mining-qa-lab` repository.
- 2026-08-10: Reconciled opt-in upgrade, artifact roles, paced upload,
  shell-free flashing, reboot/version verification, and no automatic rollback.
