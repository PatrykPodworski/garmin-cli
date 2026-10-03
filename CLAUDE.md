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

## Checks

- `uv sync`
- `uv run mypy`
- `uv run pytest`
