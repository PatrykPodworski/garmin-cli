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

## Testing

- Tests never touch the network. Pass a fake client to `main` through its
  `connect` argument.
- Fixtures are minimal hand-written dicts with made-up values, under the
  anonymization rule above.
- Each subcommand tests its happy path, its "not synced / missing field" path,
  and `--raw` where it exists.
- `uv run pytest` fails when branch coverage of `src/` drops below 90%.

## Checks

- `uv sync`
- `uv run mypy`
- `uv run pytest`
- `uv run ruff check`
- `uv run ruff format --check`
