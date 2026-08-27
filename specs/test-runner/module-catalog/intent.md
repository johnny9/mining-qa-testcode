# Module catalog — intent

## Problem

Gate authors currently retype Testcode file patterns and capability names and
cannot see which non-secret module settings are valid. That duplicates runner
knowledge in Status and makes stale or unsafe definitions likely.

## Why it matters

A reviewed catalog lets Status present modules and options as selections while
the exact Testcode checkout still validates every selected value before device
creation. Repository scanning must never execute repository code or expose Lab
profiles, credentials, device coordinates, or topology.

## Stakeholders

- **Gate author** — selects a named module and bounded options.
- **Test author** — maintains metadata with the module implementation.
- **Status** — reads one allowlisted file through its repository-scoped GitHub
  App installation.
- **Lab and runner** — independently validate frozen selections before HIL.

## Desired outcome

One versioned JSON file describes stable module identity, display copy, safe
discovery pattern, public capability requirements, and portable scalar options.
Status freezes selected IDs and values; Testcode rejects unknown, mistyped, or
out-of-range values before constructing a device.

## Primary flow

1. A test author changes a module and its catalog entry in the same revision.
2. Status reads the bounded catalog at an exact Git commit and renders choices.
3. A gate author selects modules and optional portable values.
4. The Lab supplies one selection to the exact-SHA Testcode process.
5. Testcode validates and overlays only catalog-declared values onto the
   selected module's ordinary profile settings.

## Alternate and failure flows

- Invalid, oversized, duplicate, unknown, or secret-like catalog fields fail
  discovery.
- A selection that does not match the runner checkout fails before hardware.
- Missing optional values retain the module's profile/default behavior.

## Non-goals

- Discovering devices or private Lab bindings.
- Publishing pool identities, hosts, usernames, passwords, environment names,
  or executable commands.
- Importing or executing Testcode on Status.
