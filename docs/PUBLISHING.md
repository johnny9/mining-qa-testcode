# Publishing results

Publishers run after the tests, including when a test fails. Each enabled
publisher receives the same sanitized result.

Set `required = true` when a missing result must make the command fail. Local
artifacts remain available even when a remote publisher fails.

## Local report

Enable the local publisher:

```toml
[publishers.local]
enabled = true
required = true
filename = "report.html"
json_filename = "result.json"
```

Both files are written inside the timestamped run directory under
`artifacts/`.

`report.html` shows test outcomes, telemetry charts, event markers, and links
to local evidence. `result.json` contains the same result for automation.
Skipped tests use a neutral status and do not count as failures.

## Mining QA Status

Use this publisher for the durable, searchable result page:

```toml
[publishers.mining_qa_status]
enabled = true
required = true
base_url = "https://mining-qa-status.vercel.app"
token_env = "MINING_QA_TOKEN"
repository_env = "GITHUB_REPOSITORY"
commit_sha_env = "GITHUB_SHA"
target_type = "bitaxe"
target_name = "Bitaxe Bonanza 1002"
suite = "mining-qa-testcode"
upload_artifacts = true
```

Supply the token and source revision through environment variables:

```bash
read -rsp 'Mining QA publisher token: ' MINING_QA_TOKEN
export MINING_QA_TOKEN
export GITHUB_REPOSITORY='owner/firmware-repository'
export GITHUB_SHA="$(git -C /path/to/firmware-repository rev-parse HEAD)"
miner-test --config config.local.toml
```

Do not put the token in a command argument or configuration file.

The publisher:

1. creates or updates the detailed result through `/api/v1/results`;
2. asks the service for a signed upload URL for each selected artifact;
3. uploads each file directly to private storage;
4. completes each artifact reservation.

`artifact_globs` controls which files are uploaded. Typical choices include
the HTML and JSON reports, runner events, test logs, device state, telemetry,
serial output, device logs, and Stratum evidence.

When `GITHUB_RUN_ID` is present, another publication from the same repository
and run ID updates the existing result.

## GitHub Check Run

Enable direct GitHub Check publication when the runner has a GitHub App
installation token:

```toml
[publishers.github]
enabled = true
required = true
name = "mining-qa-testcode / hardware-e2e"
token_env = "GITHUB_TOKEN"
repository_env = "GITHUB_REPOSITORY"
sha_env = "GITHUB_SHA"
```

A GitHub Actions workflow must grant:

```yaml
permissions:
  contents: read
  checks: write
```

The workflow's `GITHUB_TOKEN` can create the Check Run with that permission. A
normal personal access token cannot create a Check Run. For a local runner, use
a GitHub App installation token.

The check is created in its final state and includes the test table. When
Mining QA Status also succeeds, its result page becomes the check details link.

## Source identity checks

Before a remote publisher runs, testcode checks its own repository:

- `origin` must identify the expected GitHub repository;
- `HEAD` must be an exact commit;
- tracked testcode files must be clean;
- the commit must appear in a local `origin/*` reference.

Remote publication stops if these checks fail. A published result records both
the firmware source revision under test and the exact testcode revision that
ran it. Test names link to the source line at that testcode commit.

## Privacy

Result summaries, structured checks, and telemetry can be public. Before remote
publication, the runner removes or replaces:

- configured pool identities;
- configured secrets;
- private IP and device information;
- unrelated absolute paths;
- local artifact paths.

Raw logs and selected evidence should be uploaded as private artifacts. Do not
write passwords, tokens, private device addresses, or other secrets into test
names, chart markers, summaries, or custom result fields.

## Runs started by mining-qa-lab

An orchestrated run follows the same publishing rules.

- Testcode publishes the detailed child result to Mining QA Status.
- Testcode writes a bounded result pointer for the lab.
- Testcode writes an artifact manifest for the lab's verified private copy.
- The lab links the child result to its parent gate.

The lab archive is redundancy only. It never replaces the required detailed
publication. A missing required Mining QA Status result makes the assignment
fail even when the local lab copy is complete.
