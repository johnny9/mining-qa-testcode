# Module catalog — risks and scope

## Scope

### In

- Versioned module metadata, portable scalar option declarations, strict
  selection parsing, and configuration overlay.

### Out

- Private Lab binding, device discovery, credentials, source checkout, and
  central trigger policy.

## Assumptions

- Status reads only from a configured GitHub App repository installation.
- Lab still pins and verifies the exact Testcode checkout used by the runner.

## Open questions

- None for schema v1; later conditional or structured options require a new
  version rather than loosening v1.

## Failure modes

| Failure | Impact | Detection | Mitigation or recovery |
|---|---|---|---|
| Catalog drifts from code | Gate offers an invalid module/option | exact-checkout runner validation | fail before hardware and update catalog with code |
| Private setting is cataloged | Sensitive topology enters central policy | key denylist and review | reject catalog; keep value in Lab profile |
| Branch moves after discovery | UI metadata differs from execution | exact catalog commit and Lab checkout validation | refresh and publish a new immutable revision |
| Option is out of bounds | Unsafe or excessive test behavior | strict type/range validation | reject before discovery/device creation |

## Security, privacy, and safety

- Catalogs contain no values from a Lab profile or environment.
- Portable options can tune an already-authorized module but cannot name a
  device, endpoint, credential, command, path, pool, or identity.
- Testcode remains the final validator before hardware creation.

## Performance and resource risks

Byte, count, and string bounds prevent repository metadata from becoming an
unbounded Status or runner input.

## Rollout and rollback

Deploy the optional Testcode reader before Status writes selections. Roll back
Status selection writing first; removing the environment payload restores the
existing runner path without a profile migration.
