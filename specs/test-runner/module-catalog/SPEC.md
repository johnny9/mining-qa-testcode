# Module catalog

Publish bounded, versioned Testcode module metadata so trusted coordinators can
build gates without importing runner code or retyping patterns and options.

- **Lifecycle:** supported
- **Owner:** test-runner maintainers
- **Last reconciled:** 2026-09-13
- **Spec ID:** TR-CATALOG

[Intent](intent.md) · [Acceptance](acceptance.md) · [Design](design.md) ·
[Risks](risks.md)

## Changelog

- 2026-09-13: Registered bounded SV1 timestamp rolling, healthy reconnect
  cycles, and job burst options; strict timestamp checking remains the default.
- 2026-09-11: Registered authenticated SV2 pool fallback with the existing
  bounded fallback options and a distinct `stratum-v2` capability requirement.
- 2026-09-11: Exposed bounded fallback stability, cycle count, and outage
  duration options for the expanded regression scenarios.
- 2026-09-11: Added pool fallback regression with bounded phase timeout and
  share difficulty; enablement and endpoint settings remain in private profiles.
- 2026-09-04: Added the Stratum V2 regression module with a bounded channel
  enum, difficulty values, and waits while keeping endpoints and identities in
  private profiles.
- 2026-08-27: Implemented and validated the strict packaged catalog, portable
  option selection, pre-device module validation, and exact-source coordinator
  boundary.
- 2026-08-27: Defined the repository-scannable v1 module catalog and bounded
  portable option override contract for Status-owned gate configuration.
