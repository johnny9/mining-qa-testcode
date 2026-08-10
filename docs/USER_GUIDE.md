# Test runner user guide

This guide explains how to configure and run `miner-test`. It is for people
using the test runner. Internal design and contributor rules remain in the
[specifications](../specs/README.md).

## Before you start

You need:

- Python 3.11 or newer;
- network or serial access to an authorized mining device;
- a local TOML configuration file;
- any required passwords or publishing tokens in environment variables.

A normal run may change pool settings, restart the device, or install firmware.
The runner tries to restore mutable settings after every test, including a
failed test. Confirm the target device and configuration before starting.

## Install the runner

From the repository:

```bash
python3 -m venv .venv
. .venv/bin/activate
python3 -m pip install -e .
```

Copy an example configuration:

```bash
cp configs/bitaxe-bonanza.example.toml config.local.toml
```

Keep the local file untracked. It contains private hostnames, device names, and
paths.

## Configure a device

A basic Bitaxe Bonanza entry looks like this:

```toml
[[devices]]
name = "bonanza-lab-1"
type = "bitaxe_bonanza"

[devices.interfaces.api]
base_url = "http://bitaxe.local"

[devices.interfaces.websocket]
enabled = true
required = false

[devices.options]
read_only = false
publication_name = "Bitaxe Bonanza 1002"

[devices.interfaces.serial]
port = "/dev/serial/by-id/usb-Espressif_USB_JTAG_serial_debug_unit_*-if00"

[devices.interfaces.upgrade]
enabled = false
method = "ota"
```

Use a stable `/dev/serial/by-id/` path when serial access is enabled. The
WebSocket URL is derived from the API address when it is not set.

`publication_name` is the safe device label shown in reports. The private
configuration name stays local. Published evidence also removes private IP
addresses, MAC addresses, Wi-Fi information, pool identities, and local paths.

### Bitaxe Gamma 602

Use `type = "bitaxe_602"` for a Gamma board 602 with a BM1370 ASIC. This board
uses the normal ESP-Miner application and AxeOS files. Do not configure a
separate bridge firmware file.

## Supply secrets

Use an environment variable reference instead of writing a secret in TOML:

```toml
[tests.public_pool_smoke]
host = "public-pool.io"
port = 3333
username_env = "MINER_TEST_POOL_USER"
configure_device = true
```

Set the value in the shell before the run:

```bash
export MINER_TEST_POOL_USER='your-test-identity'
```

When `configure_device = true` and no username is supplied in configuration or
the environment, the smoke test preserves the device's current pool username
while applying the configured host and port. A separate `probe_username` is
used only by the independent Stratum probe and is never written to the device.

Passwords use the same pattern. The default variable is
`MINER_TEST_POOL_PASSWORD`.

A pool password is not written to a device unless
`configure_device_password = true`. AxeOS does not return the current
write-only password. If a test changes it, set
`devices.options.baseline_stratum_password_env` so the runner can restore the
original value from process memory.

Do not put passwords, tokens, or resolved secret values in the configuration
file or command arguments.

## Use read-only mode

Set:

```toml
[devices.options]
read_only = true

[tests.public_pool_smoke]
configure_device = false
```

Read-only mode rejects API writes and firmware uploads. The device must already
use the expected pool host and port.

This mode observes the device; it does not promise to repair a device that was
already in an unexpected state.

## Configure firmware installation

Firmware installation is off by default.

For OTA, configure an application image and, when needed, a web image. The web
image is uploaded before the application image. After reboot, the runner checks
the reported version.

For USB flashing, configure the serial interface and a command that uses named
placeholders such as `{port}`, `{factory}`, `{application}`, or `{web}`.
The runner does not use a shell to run the command.

The installed firmware becomes the run baseline. Tests restore mutable device
settings but do not flash the previous firmware after every test.

## Run tests

Run the full configured suite:

```bash
miner-test --config config.local.toml
```

Without installing the package:

```bash
PYTHONPATH=src python3 -m miner_testcode --config config.local.toml
```

Select one device:

```bash
miner-test --config config.local.toml --device bonanza-lab-1
```

Select one test file:

```bash
miner-test --config config.local.toml \
  --pattern 'test_public_pool_smoke.py'
```

### Run optional pull-request validation

Some regression cases are present but disabled until the firmware change they
check is selected. Enable cases for one pull request:

```bash
miner-test --config config.local.toml --validation-pr 1849
```

The option can be repeated. For a saved local profile, add the pull request
numbers under `[runner]`:

```toml
[runner]
validation_prs = [1849]
```

Cases for other pull requests stay visible as skipped tests. Skips are neutral
and are not counted as failures.

## Understand the test lifecycle

A device adapter reports the capabilities that its configured interfaces can
support. Each test declares the capabilities it needs. A test is skipped when
the device cannot provide them.

For an active test, the runner:

1. opens the required interfaces;
2. records the starting pool, pause state, and other mutable settings;
3. runs the test while API, WebSocket, and serial monitors collect evidence;
4. restores the saved settings;
5. closes the interfaces;
6. records the outcome and any cleanup error.

A cleanup error is reported as an error. It is never hidden by an earlier test
result.

## Read local results

Every command creates one timestamped directory below `artifacts/`. The local
publisher normally writes:

- `report.html`: a browser report with test outcomes, charts, and artifact
  links;
- `result.json`: the same result in a machine-readable form;
- `test.log`: messages from one test;
- `device-state.jsonl`: normalized device state over time;
- `telemetry.jsonl`: detailed metric samples;
- `api.jsonl`: bounded API request records;
- `serial.log`: captured serial output;
- the starting-settings record and downloaded device log.

An orchestrated run also writes `orchestration-artifacts.json`. The file lists
safe relative artifact paths, sizes, media types, and SHA-256 digests so the lab
can verify its private copy.

See [Publishing results](PUBLISHING.md) for remote outputs and
[Stratum tests](STRATUM_TESTS.md) for pool-related tests.

## Common problems

### The runner skips a test

Check the reason in `report.html`. The device may lack a required interface or
capability, or the test may require an unselected pull-request number.

### Read-only mode blocks the run

The configuration requested a write, restart, pool change, or firmware upload.
Use an observational test configuration or, only for an authorized target,
turn off read-only mode.

### Cleanup reports an error

Do not assume that the device is ready for another run. Inspect its current
pool, pause state, firmware, network reachability, and logs before reusing it.

### Remote publication fails

Local artifacts are still kept. When a publisher is marked `required = true`,
the command also exits unsuccessfully. Fix the publisher configuration or
service problem before treating the run as complete.
