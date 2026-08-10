---
name: configure-mining-test-device
description: Walk a user through creating and safely validating an ignored local mining-qa-testcode TOML profile for a supported local device. Use when selecting a device adapter, configuring API/WebSocket/serial/upgrade interfaces, mapping exact firmware artifacts, choosing tests and publishers, keeping secrets in environment variables, or preparing a reusable handoff before a local mining hardware test.
---

# Configure a mining test device

Create a minimal local profile from current repository contracts and live,
read-only evidence. Adapt to any registered adapter and example profile; do not
hard-code one miner model.

## Discover supported configuration

1. Read `AGENTS.md`, the configuration section of `README.md`, matching files
   under `configs/`, and the current device registry in
   `src/miner_testcode/devices/`.
2. Inspect the selected E2E test's `required_capabilities` and settings access.
3. Match the physical device identity to a registered `type`. If none matches,
   stop and explain that a new adapter is required instead of fabricating TOML.
4. Use the closest checked-in example as a base and retain only interfaces,
   tests, and publishers relevant to the intended run.

Treat example hosts, serial paths, usernames, versions, and artifact paths as
placeholders until verified.

## Collect safe inputs

Establish:

- A private config name and stable non-sensitive `publication_name`.
- API endpoint and, when supported, WebSocket endpoint.
- Stable serial identity such as `/dev/serial/by-id`; avoid volatile tty names.
- Intended test module, optional validation PRs, and whether device mutation is
  authorized.
- Pool and password environment-variable names, never secret values in chat or
  committed TOML.
- Publisher destinations and whether remote publication is intended.
- Exact artifact handoff, installation method, expected version, and recovery
  plan if firmware deployment is intended.

Use safe GETs, local device enumeration, and adapter source to resolve facts
when authorized. Never change a device while creating or validating a profile.

## Create the profile

Write `config.<descriptive-name>.local.toml` in the repository unless the user
specifies another ignored path. Confirm it is ignored before adding private
coordinates. Never commit local profiles, tokens, device addresses, or artifact
paths.

Configure these boundaries deliberately:

- Keep local publisher enabled. Disable remote publishers unless the user
  intends that run to publish.
- Default to `devices.options.read_only = true` for observational tests.
- Set `read_only = false` only when the chosen test requires mutation and the
  user authorized writes with a cleanup baseline.
- Keep `devices.interfaces.upgrade.enabled = false` unless the run must install
  the exact verified artifact handoff.
- Resolve relative paths from the profile directory. Map each artifact only to
  a role the selected adapter supports.
- Use exact `${ENV_NAME}` values or documented `*_env` keys for secrets. Do not
  partially interpolate or print resolved values.
- Use the host address reachable from the device for a local fake pool; never
  use `127.0.0.1` unless the miner runs on that same host.
- Configure a write-only temporary password only with an in-memory source for
  the original value so cleanup can restore it.

Firmware becomes the run baseline and is not automatically rolled back. Make
that persistence explicit to the user.

## Validate without touching hardware

1. Parse the TOML.
2. Load it through `miner_testcode.config.load_config` when required environment
   variables are available; otherwise report their names as prerequisites.
3. Verify the selected device exists and is enabled, paths resolve as intended,
   artifacts exist and match the artifact handoff, test discovery matches at
   least one module, and the serial glob resolves unambiguously when required.
4. Check that mutation, upgrade, publisher, and recovery choices agree with the
   requested test.
5. Inspect the profile for literal secrets, placeholder values, volatile device
   paths, and accidental remote publication.

Do not use `miner-test` as a config validator: it constructs devices and runs
hardware tests.

## Hand off

Report:

- Local profile path, selected adapter/device, test pattern, and validation PRs.
- Read-only/write scope, firmware-deployment state, exact artifact hashes if
  enabled, expected persistent firmware outcome, and recovery path.
- Required environment-variable names without values.
- Publisher destinations and whether the next run has external side effects.
- Validation performed and any item still needing live confirmation.

Pass this profile handoff to `$run-mining-device-test`. Do not run the test as
part of configuration unless the user also requested it.
