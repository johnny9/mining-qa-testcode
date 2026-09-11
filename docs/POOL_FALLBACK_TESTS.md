# Pool fallback tests

The pool fallback module checks manual switching, automatic fallback/recovery,
edits without role changes, saves with manually preferred fallback, and
correction of an unavailable primary. Separate cases restore either endpoint
after both pools are down, repeat failover cycles, and exercise a primary that
keeps its TCP connection open but stops replying. The PR 1957/1962 option adds
the original settings-save and role-swap scenario.

Each phase requires the expected saved preference and active pool, fresh work,
a new submission to the expected local server, and new accepted shares reported
by the miner. A settings save may reconnect or trigger a probe; either is valid
if mining resumes on the correct pool within the deadline.

By default each phase also requires five seconds of stable selection, a later
job, and additional accepted shares. Configure `stable_seconds` (0–60, below
`phase_timeout`), `transition_cycles` (2–5, default 3), and `outage_seconds`
(15–180, default 45) to adjust the bounded scenarios. A zero stability window
retains the original single-transition check.

Copy `configs/pool-fallback.example.toml` to an ignored local profile. Set the
device address, a test-host address reachable from the miner, and `enabled=true`.
Allow the miner to connect to both test ports. `primary_port` and `fallback_port`
default to automatically chosen ports; set two distinct fixed ports when host
firewall rules require them. Local listener startup alone does not prove the
miner can reach those ports.

The module catalog exposes phase timeout, share difficulty, stability window,
cycle count, and outage duration. Enablement and device and test-host settings
remain in your local profile.

The device must already be hashing, be unpaused, and have three unused pool slots. The test creates
temporary entries, preserves original pool entries and passwords, then restores
selection and removes the temporary entries after each case.

Run the ordinary regression:

```sh
.venv/bin/miner-test --config config.pool-fallback.local.toml
```

Include the settings/role-swap validation:

```sh
.venv/bin/miner-test --config config.pool-fallback.local.toml --validation-pr 1962
```

`--validation-pr 1957` selects the same additional case. These options select
tests; they do not install firmware. Pin `expected_hostname` and
`expected_version` to validate a specific installed target.

For rendered dashboard checks, open the miner's root dashboard URL in a browser
whose Chrome DevTools endpoint listens only on loopback, then set
`dashboard_cdp_url`. Manual switches use the dropdown. A separate browser case
edits pool workers, swaps roles in both directions across two saves in the same
form, reloads, edits again, saves, and verifies persistence. While the settings
page is open it checks the form's roles and device mining state; dashboard
phases check the active label. Without a browser, that form case skips before
hardware setup and other cases use the API.

The real pool form normally submits every row. A browser request guard forwards
only the disposable rows and the submitted role indices. It omits unchanged
original rows, masked passwords, and unused protocol defaults, and rejects
unexpected writes. The form's edits and selection are validated against the
device after the actual Save request. Password editing and unrelated protocol
options are outside this browser scenario.

Artifacts include phase and outage observations, browser-save evidence, both sanitized Stratum transcripts,
cleanup verification, and the runner's usual telemetry and device logs. A
cleanup failure makes the run unsuccessful even if all phases passed. Normal
mining is interrupted temporarily; run on an authorized idle lab target.

Cleanup also requires fresh accepted shares after restoration. If the miner
receives work but remains at zero hashrate for 30 seconds, the module attempts
one recovery restart and verifies the original settings again. A required
recovery restart is reported as an error even if mining resumes; it is never
silently counted as a pass. Devices reporting safety faults are not restarted
by this recovery path.
