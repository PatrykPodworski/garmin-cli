# garmin-cli

`garmin` reads your Garmin Connect data and prints it as JSON. It can also adjust a
night's sleep times. Scripts, agents and people at a terminal can use it. It wraps
[python-garminconnect](https://github.com/cyberjunky/python-garminconnect).

## Install

```sh
uv tool install git+https://github.com/PatrykPodworski/garmin-cli
```

This puts `garmin` on your `PATH`. From a clone, run it with `uv run garmin` instead.

## Log in

Login works on macOS only, because the password comes from the Keychain.

```sh
security add-generic-password -s garmin -a you@example.com -w  # prompts for the password
export GARMIN_EMAIL=you@example.com
garmin login
```

`garmin login` asks for an MFA code if your account has one. It saves tokens to
`~/.garminconnect`, or to the path in `GARMINTOKENS` if you set it. The other
commands read those tokens. When the tokens expire, a command fails and tells you to
run `garmin login` again.

| Message starts with | Fix |
|---|---|
| `Not logged in` | Run `garmin login`. |
| `GARMIN_EMAIL is not set` | `export GARMIN_EMAIL=you@example.com` |
| `No Keychain password` | Add it with the `security add-generic-password` line above. |
| `'garmin login' reads the password from the macOS Keychain` | Log in on a Mac and copy the token folder, or point `GARMINTOKENS` at a copy. With `GARMINTOKENS` set, the message says to copy a token folder from a Mac and point `GARMINTOKENS` at it. |
| `Garmin rejected the login` | Fix the Keychain password, then run `garmin login`. |
| `No MFA code entered` | Run `garmin login` in a terminal and type the code. |
| `Garmin is rate-limiting logins` | Wait about an hour, then run `garmin login`. |

## Dates

Every date argument takes `today`, `yesterday` or `YYYY-MM-DD`.

## Commands

### stats

```sh
garmin stats              # today
garmin stats yesterday
garmin stats 2026-07-05
```

```json
{
  "date": "2026-07-05",
  "total_kcal": 2450,
  "active_kcal": 620,
  "bmr_kcal": 1830,
  "resting_hr": 54,
  "body_battery_high": 88,
  "body_battery_low": 21,
  "avg_stress": 31
}
```

The daily summary: calories, resting heart rate, the day's highest and lowest body
battery, and average stress. A day that has not synced yet exits with status 1.

### sleep

```sh
garmin sleep 2026-07-05             # the night you woke up from on July 5
garmin sleep --night-of 2026-07-04  # the same night, by its lights-out date
garmin sleep                        # last night
```

```json
{
  "date": "2026-07-05",
  "start": "23:10",
  "end": "06:45",
  "duration_min": 410,
  "deep_min": 85,
  "light_min": 230,
  "rem_min": 95,
  "awake_min": 45,
  "score": 81,
  "scores": {
    "rem_percentage": {"value": 22, "qualifier": "EXCELLENT"},
    "stress": {"value": null, "qualifier": "FAIR"}
  }
}
```

Garmin files a night under its wake-up date, so the positional date is the morning
you woke up. `--night-of DATE` takes the date you went to bed and queries DATE+1.
`start` and `end` are local `HH:MM`, `duration_min` is time asleep, and the `*_min`
stages are `null` when Garmin has no value. `score` is the overall sleep score, and
`scores` holds the sub-scores, each with `value` and `qualifier`. A night that has
not synced yet exits with status 1.

### sleep set

```sh
garmin sleep set 2026-07-05 --start 23:10 --end 06:45             # by the wake-up date
garmin sleep set --night-of 2026-07-04 --start 23:10 --end 06:45  # by the lights-out date
```

Moves a night's sleep window on Garmin Connect, like "Adjust sleep times" in the
Garmin Connect app, then prints the night as `garmin sleep` does. The date works as
in `garmin sleep` and defaults to today. `--start` and `--end` are both required,
in local `HH:MM`. The end is on the wake-up date; a start earlier than the end is on
the same date, and a later one is on the evening before. Garmin Connect recomputes
the sleep stages at once, but the sleep score may update later. A start equal to
the end exits with status 2, and a night that has not synced exits with status 1.

### weight

```sh
garmin weight                                    # today
garmin weight --from 2026-07-01 --to 2026-07-05
```

```json
[
  {
    "date": "2026-07-05",
    "time": "07:35:00",
    "weight_kg": 72.4,
    "body_fat_pct": 19.2,
    "muscle_mass_kg": 32.1,
    "body_water_pct": 56.0
  }
]
```

One record per weigh-in, with local time. A scale that does not measure body
composition leaves those fields `null`. A range with no weigh-ins prints `[]`.

### bp

```sh
garmin bp                   # today
garmin bp --from yesterday  # --to defaults to today
```

```json
[
  {
    "date": "2026-07-05",
    "time": "08:15:00",
    "systolic": 120,
    "diastolic": 78,
    "pulse": 64,
    "notes": null
  }
]
```

One record per reading, with local time. A range with no readings prints `[]`.

### activities

```sh
garmin activities                                 # the 20 most recent
garmin activities --type running --limit 5
garmin activities --from 2026-07-01 --to 2026-07-05
```

```json
[
  {
    "id": 1234567890,
    "date": "2026-07-05 07:00:00",
    "name": "Morning Run",
    "duration_s": 2100.0,
    "distance_m": 7000.0,
    "avg_hr": 148.0,
    "max_hr": 171.0,
    "elevation_gain_m": 45.0,
    "calories": 480.0,
    "aerobic_te": 3.0,
    "anaerobic_te": 0.8,
    "vo2max": 48.0,
    "type": "running",
    "avg_pace_s_per_km": 300
  }
]
```

Activities come newest first. `--type` takes a Garmin activity type such as
`running`, `cycling` or `swimming`. `--limit` caps the count (default 20).
Running activities get `avg_pace_s_per_km`; other types get `avg_speed_kmh`. A key
Garmin has no value for is left out.

### activity

```sh
garmin activity 1234567890
```

```json
{
  "id": 1234567890,
  "date": "2026-07-05T07:00:00.0",
  "name": "Morning Run",
  "duration_s": 2100.0,
  "aerobic_te": 3.0,
  "type": "running",
  "avg_pace_s_per_km": 300,
  "laps": [
    {"duration_s": 300.0, "distance_m": 1000.0, "avg_hr": 142.0, "max_hr": 150.0, "avg_pace_s_per_km": 300}
  ],
  "hr_zones": [
    {"zone": 1, "seconds": 240.0, "low_bpm": 98}
  ]
}
```

One activity by the `id` from `garmin activities`. It has the same keys as an
`activities` item, plus `laps` (the same keys per lap, without `type`) and
`hr_zones` (seconds spent in each zone and the zone's lower bound in bpm).

## Raw output

`stats`, `sleep`, `weight`, `bp`, `activities` and `activity` accept `--raw`. It
prints the full Garmin response instead of the summary. `activity --raw` combines
three responses under `summary`, `splits` and `hr_zones`. `stats --raw` skips the
not-synced check.

## Output and exit codes

Results go to stdout as JSON. Summary floats are rounded to two decimals; `--raw`
output is not. Errors go to stderr as one line,
`garmin: <What happened.> <What to do.>`.

| Code | Meaning | Example |
|---|---|---|
| 0 | Success | JSON on stdout |
| 1 | Garmin error, data not synced yet, login error, or a bug | `garmin: Not logged in: no valid saved login in ~/.garminconnect. Run 'garmin login'.` |
| 2 | Bad arguments | `garmin: Unknown command 'slep'. Did you mean 'sleep'?` |

Messages for status 1:

| Case | Message |
|---|---|
| `stats` day not synced | `garmin: No daily summary for <date> yet. Sync your watch with Garmin Connect, then try again.` |
| `sleep` night not synced | `garmin: No sleep data for the night ending <date> yet. Sync your watch with Garmin Connect, or use --night-of if <date> is the night you went to bed.` |
| `sleep --night-of` night not synced | `garmin: No sleep data for the night of <date> yet. Sync your watch with Garmin Connect, then try again.` |
| `sleep set` night has no time zone | `garmin: Garmin Connect sent no time zone for the night ending <date>, so garmin-cli cannot convert the times. Adjust the sleep times in the Garmin Connect app.` |
| `activity <id>` not found | `garmin: No activity with ID <id>. Run 'garmin activities' to list recent IDs.` |
| Rate limit | `garmin: Garmin is rate-limiting requests from this machine. Wait a few minutes and try again.` |
| Tokens expired | `garmin: Not logged in: no valid saved login in ~/.garminconnect. Run 'garmin login'.` |
| Unreadable response | `garmin: Garmin Connect sent a response garmin-cli could not read. Try again in a few minutes; if it keeps failing, rerun with --debug and report it at https://github.com/PatrykPodworski/garmin-cli/issues.` |
| Network failure | `garmin: Could not reach Garmin Connect (<reason>). Check your internet connection and try again.` |
| Bug in garmin-cli | `garmin: Unexpected error (<reason>). Rerun with --debug and report it at https://github.com/PatrykPodworski/garmin-cli/issues.` |

`<reason>` is `<error type>: <first line of the message>`, with URL query strings
shortened to `?…`, `Bearer` values to `Bearer …`, and the whole cut to 100 characters.

`garmin --debug <command>` prints the full Python traceback for an unexpected error
instead of the one-line message.

## Use from an agent

`skills/garmin/SKILL.md` tells Claude Code and similar agents when and how to call
`garmin`. Install it from a clone:

```sh
ln -s "$PWD/skills/garmin" ~/.claude/skills/garmin
```

## Development

```sh
uv sync
uv run mypy
uv run pytest
uv run ruff check
uv run ruff format --check
uv run vulture
uv run deptry src
```

Test and fixture rules are in [CLAUDE.md](CLAUDE.md).
