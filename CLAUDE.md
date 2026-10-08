# garmin-cli

Tracker: GitHub Issues

This repository is public. Never commit real Garmin data.

- Test fixtures and examples copied from real Garmin responses must be anonymized
  before commit: replace weight, blood pressure, heart rate, sleep times, GPS
  coordinates/polylines, activity names, device serials, user/profile IDs, and
  display names with made-up values. Keep only the fields the test needs.
- Tokens (`~/.garminconnect`) and passwords (macOS Keychain) stay outside the repo.
  Never print them in logs or error messages.
- Command output pasted into issues or PRs follows the same rule.

## Modules

Read commands are grouped by domain, one module per group (`health.py`, `sleep.py`, …).
A command that changes Garmin data gets its own module, named `<group>_<verb>.py`, and
imports shared read helpers from its group. Time and date conversion lives in `dates.py`.

## Testing

- Tests never touch the network. Pass a fake client to `main` through its
  `connect` argument.
- Fixtures are minimal hand-written dicts with made-up values, under the
  anonymization rule above.
- Each subcommand tests its happy path, its "not synced / missing field" path,
  and `--raw` where it exists.
- `uv run pytest` fails when branch coverage of `src/` drops below 90%.

## Checks

CI (`.github/workflows/ci.yml`) runs these on every pull request and push to `main`.

- `uv sync`
- `uv run mypy`
- `uv run pytest`
- `uv run ruff check`
- `uv run ruff format --check`
- `uv run vulture`
- `uv run deptry src`
- `uv run mutmut run` (score ≥ 80%, see below)

## Mutation testing

The CI `check` job runs `mutmut` on every pull request and push to `main` and fails
when the score (killed / (killed + survived + timeout + suspicious)) falls below 80%.
Run it locally with `uv run mutmut run`, then `uv run mutmut results` lists the
surviving mutants and `uv run mutmut show <name>` shows one.
