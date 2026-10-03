# garmin-cli

`garmin` — read Garmin Connect data from the terminal as JSON: activities,
sleep (with sleep score), weight, blood pressure, daily stats.

Thin wrapper over [python-garminconnect](https://github.com/cyberjunky/python-garminconnect).
Built to be called by scripts and agents.

## Sleep

```sh
garmin sleep 2026-07-05             # the night you woke up from on July 5
garmin sleep --night-of 2026-07-04  # the same night, by its lights-out date
garmin sleep 2026-07-05 --raw       # full Garmin response, per-minute arrays included
```

Garmin files a night under its wake-up date, so the positional date is the morning
you woke up. `--night-of DATE` takes the date you went to bed and queries DATE+1.
Output keys: `date` (Garmin's wake-up date), `start` and `end` (local `HH:MM`),
`duration_min` (time asleep), `deep_min`, `light_min`, `rem_min`, `awake_min`,
`score` (overall sleep score), and `scores` (sub-scores, each with `value` and
`qualifier`). A night that has not synced yet exits with status 1.

## Weight and blood pressure

```sh
garmin weight --from 2026-07-01 --to 2026-07-05  # one record per weigh-in
garmin bp --from yesterday                       # --to defaults to today
garmin weight --raw                              # full Garmin response
```
