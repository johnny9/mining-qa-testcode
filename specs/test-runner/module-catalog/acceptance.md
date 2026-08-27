# Module catalog — acceptance

## Functional behavior

- [x] **TR-CATALOG-AC-01:** The package contains one schema-version-1 catalog
  with unique bounded modules, safe unittest discovery patterns, required
  coordination capabilities, and portable option declarations.
- [x] **TR-CATALOG-AC-02:** A strict parser rejects unknown fields, duplicate
  module/option IDs, invalid defaults, unsafe patterns, oversized catalogs, and
  option values outside their declared type, enum, or numeric bounds.
- [x] **TR-CATALOG-AC-03:** A bounded module-selection environment payload
  overlays only the selected module's declared portable values onto profile
  test settings before discovery and device construction.

## Interfaces and compatibility

- [x] **TR-CATALOG-AC-04:** Status can read
  `src/miner_testcode/module-catalog.v1.json` without executing repository code;
  the file is included in wheels and sdists.
- [x] **TR-CATALOG-AC-05:** Runs without a selection payload preserve existing
  profiles and CLI behavior. Existing secret/private settings remain Lab-owned
  and cannot be declared portable.

## Quality attributes

- [x] **TR-CATALOG-AC-06:** Catalog and selection bodies are byte-bounded and
  tests prove unknown or private-looking option keys fail before hardware use.

## Verification evidence

- The complete Testcode unit suite passed all 90 tests on 2026-08-27. Focused
  catalog tests cover loading, duplicate/private option rejection, typed
  bounds, profile overlay, and selected-module pattern validation before
  device construction.
- Wheel and sdist builds passed and both include
  `miner_testcode/module-catalog.v1.json`. Status independently reads the same
  strict public shape at an exact Testcode commit, while Lab and Testcode tests
  cover the bounded selection handoff and provenance-drift rejection.

## Acceptance rule

The catalog is acceptable only when strict parser, overlay, privacy-negative,
full unit, package, and cross-project contract checks pass without HIL.
