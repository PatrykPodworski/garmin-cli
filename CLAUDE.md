# garmin-cli

Tracker: GitHub Issues

Accepted decisions: `docs/adr/README.md`; read the ADRs whose title touches your work.

This repository is public. Never commit real Garmin data.

- Test fixtures and examples copied from real Garmin responses must be anonymized
  before commit: replace weight, blood pressure, heart rate, sleep times, GPS
  coordinates/polylines, activity names, device serials, user/profile IDs, and
  display names with made-up values. Keep only the fields the test needs.
- Tokens (`~/.garminconnect`) and passwords (macOS Keychain) stay outside the repo.
  Never print them in logs or error messages.
- Command output pasted into issues or PRs follows the same rule.

## Workflow

- Sessions decide anything this file, existing code, or earlier issue answers settle.
  They escalate only product decisions, batched, with a recommendation for each.
- Commit and open PRs only as part of an issue's flow. Anything else destructive or
  outward-facing needs Patryk's yes.
- Pull requests open published and ready for review, never as drafts. Sessions
  squash-merge a PR once all its checks pass. A PR that lists a live manual test
  merges only after that test has run: by Patryk, or by a tester he allowed for that
  batch.
- Done means evidence: the checks that ran with their results, and the PR link.
- Branch: `<type>/<issue>-<slug>`, e.g. `feat/92-workout-schedule` (PRs #93–#97).
  Commit and PR title: `<type>(<scope>): <summary> (#<issue>)` (PRs #61–#97).
- Agents call the live Garmin API only when Patryk allows it for a batch or a task.
  Without that, a PR that reads or changes live data lists a manual test for Patryk
  (#63, #75, #88, #89). With it, agents work only on test records they create
  (made-up values, names starting `garmin-cli test`, weight and blood pressure on a
  past date with no other records), delete them at the end, and never change or read
  out existing records. A write that a Garmin delete does not undo, such as an upload
  that Garmin forwards to Strava, needs his yes for that write.
- Manual argument checks run with `GARMINTOKENS=/nonexistent`, so a call that gets past
  parsing stops at login (#57, #60).
- A change to a command updates `README.md` and `skills/garmin/SKILL.md` in the same PR
  (#60, #75).
- Consumers in the `ai` repo (`calories`, skills) are edited by Patryk or a session he
  allows, never by this repo's agents (#98).
- Add a runtime dependency only when the issue asks for one; issues have chosen the
  standard library or the existing client each time (#71, #75, #91).

## Commands

- Names follow gh: `<noun> <verb>`, verbs `list view create edit delete set login
  schedule unschedule calendar`, plus verbs added on purpose. New commands use it now;
  #98 renames the old ones and drops the old names without aliases.
- Every date argument takes `today | yesterday | tomorrow | YYYY-MM-DD` (#92). A
  timestamp is local `YYYY-MM-DD HH:MM`; a bare date is rejected (#62).
- Sleep is filed under the wake-up date; `--night-of DATE` takes the lights-out date (#4).
- Time zone: the machine's IANA name (`TZ`, else the `/etc/localtime` target), with
  `--tz` to override (#71).
- Ranges use `--from/--to`; `--limit` is a positive integer, default 20 (#5, #31, #89).
- `--raw` prints Garmin's response unchanged, with the help text
  `print the full Garmin response` (#31).
- Input files use `--file FILE`, `-` for stdin; `--json` is reserved for output (#75).

## Output

- Today stdout is JSON with `indent=2` and snake_case keys (#1, #3). #81 has decided the
  switch: plain text by default, `--json` for today's output, `--raw` stays JSON.
  Text tables use aligned spaces, units in the column name (`weight_kg`) with bare
  numbers, and `activity list` ends with a `total` row. #81's question 3 (how the write
  confirmation fits text output) is still open.
- Summary floats are rounded to two decimals; `--raw` is not (#50).
- A missing optional field is `null` (#3, #32); `activities` records omit it (#5).
  An empty list prints `[]` and exits 0 (#6, #89).
- A day or night that has not synced exits 1; it never prints `null` totals (#3, #4).
- Write commands:
  - Validate arguments before any client call; a bad one exits 2 (#62, #71).
  - Fetch the target first, so an unknown ID exits 1 before the write (#78, #88, #92).
  - On success, stdout shows the stored record, never `null` (#67), and stderr gets
    one `garmin: …` confirmation line (#73, batch decision on #88).
  - Delete runs without a prompt and offers `--dry-run` (#78).

## Errors

- One stderr line: `garmin: <What happened.> <What to do.>`, no usage block (#51).
- Exit 0 success, 1 Garmin, login, not-synced or unexpected error, 2 bad arguments
  (#51, #53).
- `main` catches only expected errors (#42). Anything else prints
  `garmin: Unexpected error (…)` with the issue link; `--debug` shows the traceback (#53).
- Reasons quoted from exceptions go through `reason()` in `cli.py`, which strips query
  strings and bearer tokens (#57).

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
- Use the recording `FakeClient` from `tests/conftest.py`; a new command needs no new
  fake class (#30).
- Assert every error message exactly: full stderr line, exit code, empty stdout. Help
  strings get no tests (#43).
- `GarminClient` in `client.py` lists only the methods the code calls (#41).
- `uv run pytest` fails when branch coverage of `src/` drops below 90%.

## Checks

CI (`.github/workflows/ci.yml`) runs these on every pull request and push to `main`.

- `uv sync --locked`
- `uv run mypy`
- `uv run pytest`
- `uv run ruff check`
- `uv run ruff format --check`
- `uv run vulture`
- `uv run deptry src`
- `uv run python scripts/check_adrs.py`

## Mutation testing

Pull requests do not run `mutmut`. `.github/workflows/mutation.yml` runs it on `main`
once a night, and only when `main` changed since its last completed run. The run fails
when the score (killed / (killed + survived + timeout + suspicious)) falls below 80% or
a step errors. A failed run opens an issue labeled `mutmut-nightly`, or comments on the
open one.
Run it locally with `uv run mutmut run`, then `uv run mutmut results` lists the
surviving mutants and `uv run mutmut show <name>` shows one. Kill a survivor with a
test, or name it as equivalent in the PR with the reason (#43, #83).
