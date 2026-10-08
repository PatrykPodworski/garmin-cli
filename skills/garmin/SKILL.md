---
name: garmin
description: Use when the user asks about their Garmin data — workouts (runs, rides), sleep or sleep score, weight, body fat, blood pressure, calories burned, resting heart rate, body battery or stress — or asks to adjust a night's sleep times, log a weigh-in, add a manual activity or delete an activity.
---

# garmin

`garmin` reads the user's Garmin Connect data and prints JSON. Run it with Bash.
Four commands change data: `garmin weight add`, `garmin sleep set`,
`garmin activity add` and `garmin activity delete`.

## Login

The user logs in, not you. A command that exits 1 with `Not logged in` means
the saved login is missing or expired: ask the user to run `garmin login` in their
own terminal, because it reads their Keychain password and may ask for an MFA code.
Leave the token folder (`~/.garminconnect` or `$GARMINTOKENS`) unread.

## Commands

Every date takes `today`, `yesterday` or `YYYY-MM-DD`.

```sh
garmin stats [DATE]                    # calories, resting HR, body battery, stress (default today)
garmin sleep [DATE]                    # the night that ended on the morning of DATE (default today)
garmin sleep --night-of DATE           # the night that started on the evening of DATE
garmin sleep set DATE --start HH:MM --end HH:MM  # move that night's sleep window (local times)
garmin weight --from DATE --to DATE    # weigh-ins and body composition (both default today)
garmin weight add KG [--at "YYYY-MM-DD HH:MM"] [--unit lbs]  # log a weigh-in (default now, kg)
garmin bp --from DATE --to DATE        # blood pressure readings (both default today)
garmin activities --limit 5 --type running --from DATE --to DATE  # newest first, default limit 20
garmin activity ID                     # one activity with laps and HR zones; ID from `activities`
garmin activity add --type KEY --start "YYYY-MM-DD HH:MM" --duration MIN [--distance KM] [--calories KCAL] [--name NAME]  # private manual activity
garmin activity delete ID --yes        # delete an activity; ID from `activities`
```

`garmin <command> --help` lists every flag.

## Rules

- Sleep is filed under the wake-up date. "Last night" is `garmin sleep`. Asked after
  midnight, before the user has gone to sleep, "last night" is `garmin sleep yesterday`.
  "The night of the 4th" is `garmin sleep --night-of 2026-07-04`.
- `garmin sleep set` writes to the user's Garmin account. Run it only with the date
  and both times the user gave you. It takes the same DATE or `--night-of DATE` as
  `garmin sleep`.
- `garmin weight add` writes to the user's Garmin account. Run it only with a weight
  the user gave you. After a failed run, check `garmin weight` before retrying, so the
  weigh-in is not logged twice.
- `garmin activity add` writes to the user's Garmin account. Run it only with the
  type, start and duration the user gave you. After a failed run, check
  `garmin activities` before retrying, so the activity is not created twice.
- `garmin activity delete` cannot be undone. Run it only for an activity the user
  asked you to delete, and always with `--yes`: without a terminal it exits 2 and
  asks for `--yes`. When the user names the activity by date or name, look up its ID
  with `garmin activities` and confirm the match with the user first.
- Summary floats are rounded to two decimals. Quote them as printed.
- Start with the summary. Add `--raw` only when the field you need is missing from it:
  raw output is the full Garmin response, many times larger.

## Output and errors

Results are JSON on stdout. An error is one stderr line,
`garmin: <What happened.> <What to do.>`.

Match the message first, then the exit code:

- `Unexpected error` (exit 1): a bug in garmin-cli. Show the full line to the user and stop.
- Exit 1, the second sentence names a `garmin` command other than `garmin login`
  (`Run 'garmin activities' to list recent IDs.`): run it yourself once.
- Exit 1, `or use --night-of if <date> is the night you went to bed`: run `--night-of`
  only when the user named that date as their bedtime; otherwise tell the user to sync.
- Any other exit 1 (not logged in, not synced, rate limit, no connection, unreadable
  response): tell the user the second sentence and wait for them.
- Exit 2: bad arguments. The message names the fix (`Did you mean 'sleep'?`,
  `Use today, yesterday or YYYY-MM-DD.`); correct the call and retry once.

## Privacy

The output is the user's health data. Keep it in this conversation; put it in an
issue, commit, PR or any other external place only when the user asks.
