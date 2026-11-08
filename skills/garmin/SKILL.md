---
name: garmin
description: Use when the user asks about their Garmin data — workouts (runs, rides), sleep or sleep score, weight, body fat, blood pressure, calories burned, resting heart rate, body battery, stress, training readiness, training status, training load, recovery time or HRV status — or asks to adjust a night's sleep times, log a weigh-in, add a manual activity, delete an activity, find a workout in their workout library, create or change a structured running workout, create a strength workout with exercises, sets, reps and weights, look up a strength exercise name, delete a workout, put a workout on their calendar, take it off or see what is scheduled, save a GPX file as a course, list or look up their courses, send a course to their watch, list, look up or delete their PacePro pacing plans, create a PacePro plan from a course, send a PacePro plan to their watch, or list their devices.
---

# garmin

`garmin` reads the user's Garmin Connect data and prints JSON. Run it with Bash.
Fourteen commands change data: `garmin weight add`, `garmin sleep set`,
`garmin activity add`, `garmin activity delete`, `garmin workout add`,
`garmin workout edit`, `garmin workout delete`, `garmin workout schedule`,
`garmin workout unschedule`, `garmin course create`, `garmin course send`,
`garmin pacepro create`, `garmin pacepro delete` and `garmin pacepro send`.

## Login

The user logs in, not you. A command that exits 1 with `Not logged in` means
the saved login is missing or expired: ask the user to run `garmin login` in their
own terminal, because it reads their Keychain password and may ask for an MFA code.
Leave the token folder (`~/.garminconnect` or `$GARMINTOKENS`) unread.

## Commands

Every date takes `today`, `yesterday`, `tomorrow` or `YYYY-MM-DD`.

```sh
garmin stats [DATE]                    # calories, resting HR, body battery, stress (default today)
garmin recovery view [DATE]            # training readiness, training status and load, recovery time, HRV status (default today)
garmin sleep [DATE]                    # the night that ended on the morning of DATE (default today)
garmin sleep --night-of DATE           # the night that started on the evening of DATE
garmin sleep set DATE --start HH:MM --end HH:MM  # move that night's sleep window (local times)
garmin weight --from DATE --to DATE    # weigh-ins and body composition (both default today)
garmin weight add KG [--at "YYYY-MM-DD HH:MM"] [--unit lbs]  # log a weigh-in (default now, kg)
garmin bp --from DATE --to DATE        # blood pressure readings (both default today)
garmin activities --limit 5 --type running --from DATE --to DATE  # newest first, default limit 20
garmin activity ID                     # one activity with laps and HR zones; ID from `activities`
garmin activity add --type KEY --start "YYYY-MM-DD HH:MM" --duration MIN [--distance KM] [--calories KCAL] [--name NAME]  # private manual activity
garmin activity delete ID [--dry-run]  # delete an activity; ID from `activities`
garmin workouts --limit 50              # workout library, newest created first, default limit 20
garmin workout ID                      # one workout with its steps; ID from `workouts`
garmin workout add --file FILE [--schedule DATE]  # save a workout (Garmin JSON, - for stdin), optionally on the calendar
garmin workout add --strength --file FILE [--schedule DATE]  # save a strength workout from the short format below
garmin workout edit ID --file FILE      # replace a workout with changed `workout ID --raw` JSON; keeps ID and calendar
garmin workout delete ID [--dry-run]   # delete a workout and its calendar entries; ID from `workouts`
garmin workout schedule ID DATE         # put a library workout on the calendar; ID from `workouts`
garmin workout unschedule SCHEDULE_ID   # take one entry off the calendar; schedule_id from `workout calendar`
garmin workout calendar --from DATE --to DATE  # scheduled workouts (default today to 4 weeks after --from)
garmin exercise list --search TEXT [--category CATEGORY] [--limit N]  # strength exercise names for --strength files, no login
garmin course create --file GPX [--name NAME] [--type KEY] [--privacy private|public]  # import a GPX and save it as a course (default running, private)
garmin course list --limit 50           # saved courses, default limit 20
garmin course view ID                   # one course: distance, elevation, type, privacy; ID from `course list`
garmin course send ID --device DEVICE_ID  # queue a course for a watch; DEVICE_ID from `device list`
garmin pacepro list --limit 50          # PacePro plans: course, split mode, goal time and pace; default limit 20
garmin pacepro view ID                  # one PacePro plan with each split's target pace; ID from `pacepro list`
garmin pacepro create --course ID (--goal-time H:MM:SS | --goal-pace M:SS) [--name NAME] [--dry-run]  # compute a plan with km splits and the website's default sliders from a course and save it
garmin pacepro delete ID [--dry-run]    # delete a PacePro plan; ID from `pacepro list`
garmin pacepro send ID --device DEVICE_ID  # queue a PacePro plan for a watch; DEVICE_ID from `device list`
garmin device list                      # devices on the account: id, name, model
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
- `garmin activity delete` deletes without asking and cannot be undone. Run it only
  for an activity the user asked you to delete. When the user names the activity by
  date or name instead of ID, look up its ID with `garmin activities`, run
  `garmin activity delete ID --dry-run`, and confirm the match with the user first.
- `garmin workout add` writes to the user's Garmin account. Build the workout the
  user described from the example in "Workout JSON" below, or for a strength workout
  from "Strength workout" below with `--strength`, and add `--schedule` only
  for a date the user gave. When it exits 1 after `Created workout`, the workout
  exists but is not on the calendar: tell the user, and do not run it again.
- `garmin workout edit` replaces the whole workout in the user's Garmin account.
  Run it only for a workout the user asked you to change. Round-trip it: save
  `garmin workout ID --raw` to a file, change only what the user asked, then run
  `garmin workout edit ID --file FILE` with the same ID.
- `garmin workout delete` deletes without asking and cannot be undone; Garmin also
  removes the workout's calendar entries. Run it only for a workout the user asked
  you to delete. When the user names the workout instead of giving its ID, look up
  the ID with `garmin workouts`, run `garmin workout delete ID --dry-run`, and
  confirm the match with the user first.
- `garmin workout schedule` and `garmin workout unschedule` write to the user's
  Garmin calendar. Run them only for a workout and date the user named. Before
  scheduling, check `garmin workout calendar` for that date, so the workout is not
  scheduled twice. Unschedule only an entry the user asked to remove.
- `garmin course create` writes to the user's Garmin account. Run it only for a GPX
  file the user named, with the name, type and privacy they gave; leave privacy at
  `private` unless they asked for public. Each run saves a new course, so after a
  failed run check `garmin course list` before retrying.
- `garmin course send` queues a course for a watch in the user's Garmin account.
  Run it only for a course and device the user named. Pick the device from
  `garmin device list` by the name or model the user gave; when more than one
  matches, or the user named none, ask. Success means Garmin queued the course,
  not that it is on the watch: tell the user it arrives on the watch's next sync.
  Each run queues it again, so do not retry after success.
- `garmin pacepro create` writes a new plan to the user's Garmin account. Run it
  only for a course and goal the user gave. It always makes km splits with the
  website's default sliders; for elevation splits, miles or other slider values,
  point the user to the Garmin Connect website. Run it with `--dry-run` first and
  show the user the splits. Each run saves a new plan, so after a failed run check
  `garmin pacepro list` before retrying. Its splits come from garmin-cli's own
  algorithm and differ a little from plans made on the Garmin Connect website.
- `garmin pacepro delete` deletes without asking and cannot be undone. Run it only
  for a plan the user asked you to delete. When the user names the plan instead of
  giving its ID, look up the ID with `garmin pacepro list`, run
  `garmin pacepro delete ID --dry-run`, and confirm the match with the user first.
- `garmin pacepro send` queues a PacePro plan for a watch, with the same rules as
  `garmin course send`: only a plan and device the user named, ask when the device
  is unclear, and do not retry after success. It sends only the plan: tell the user
  it arrives on the next sync, and that the plan's course has to be on the watch
  too. If the course does not arrive, offer `garmin course send` with the plan's
  `course_id` from `garmin pacepro view`.
- The CLI cannot change a PacePro plan. When the user asks for that, point them
  to Garmin Connect: Training & Planning → PacePro Pacing Strategies.
  Do not try another command or a raw request.
  Times are seconds and paces seconds per km; convert them to `h:mm:ss` and
  `m:ss /km` for the user.
- Summary floats are rounded to two decimals. Quote them as printed.
- Start with the summary. Add `--raw` only when the field you need is missing from it:
  raw output is the full Garmin response, many times larger.

## Workout JSON

`garmin workout add` takes a workout in Garmin's own format. Copy this shape and
change the names, counts and values. It has a 10-minute warm-up, 5 × (1 km at
5:10–4:50 min/km, 2 minutes recovery) and a 10-minute cool-down.

```json
{
  "workoutName": "5 x 1 km",
  "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
  "estimatedDurationInSecs": 3300,
  "workoutSegments": [{
    "segmentOrder": 1,
    "sportType": {"sportTypeId": 1, "sportTypeKey": "running"},
    "workoutSteps": [
      {"type": "ExecutableStepDTO", "stepOrder": 1,
       "stepType": {"stepTypeId": 1, "stepTypeKey": "warmup"},
       "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
       "endConditionValue": 600,
       "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}},
      {"type": "RepeatGroupDTO", "stepOrder": 2,
       "stepType": {"stepTypeId": 6, "stepTypeKey": "repeat"},
       "numberOfIterations": 5,
       "endCondition": {"conditionTypeId": 7, "conditionTypeKey": "iterations"},
       "endConditionValue": 5,
       "workoutSteps": [
         {"type": "ExecutableStepDTO", "stepOrder": 3,
          "stepType": {"stepTypeId": 3, "stepTypeKey": "interval"},
          "endCondition": {"conditionTypeId": 3, "conditionTypeKey": "distance"},
          "endConditionValue": 1000,
          "targetType": {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"},
          "targetValueOne": 3.2258,
          "targetValueTwo": 3.4483},
         {"type": "ExecutableStepDTO", "stepOrder": 4,
          "stepType": {"stepTypeId": 4, "stepTypeKey": "recovery"},
          "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
          "endConditionValue": 120,
          "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}}
       ]},
      {"type": "ExecutableStepDTO", "stepOrder": 5,
       "stepType": {"stepTypeId": 2, "stepTypeKey": "cooldown"},
       "endCondition": {"conditionTypeId": 2, "conditionTypeKey": "time"},
       "endConditionValue": 600,
       "targetType": {"workoutTargetTypeId": 1, "workoutTargetTypeKey": "no.target"}}
    ]
  }]
}
```

- `stepOrder` counts every step from 1, the steps inside a repeat group too.
- Step types: 1 warmup, 2 cooldown, 3 interval, 4 recovery, 5 rest, 6 repeat.
- End conditions: 1 lap.button (no value), 2 time (seconds), 3 distance (meters),
  7 iterations (repeat groups only).
- Targets: 1 no.target, 4 heart.rate.zone (bpm), 6 pace.zone. A pace target is in
  meters per second, 1000 / (seconds per km): `targetValueOne` is the slower pace,
  `targetValueTwo` the faster one. 5:10 min/km is 1000 / 310 = 3.2258.
- `estimatedDurationInSecs` is the sum of the steps, with the distance steps at
  their target pace.

The command prints `{"id": …, "name": …, "estimated_duration_min": …, "scheduled": …}`
and the stderr line `garmin: Created workout "5 x 1 km" (ID …).`

## Strength workout

`garmin workout add --strength --file FILE` takes this shorter format. Look up each
exercise with `garmin exercise list --search WORDS` and use a `name` it prints. The
search keeps names that contain every word, in any order, ignoring case,
punctuation and the spaces between words; a word can be part of a longer one
(`raise` finds `Banded Calf Raises`).

- The stderr line `No exercise has every word of …` means the names are only the
  closest ones. Use one only when it is clearly what the user meant; otherwise
  search with other words or ask.
- `… more exercises match. Raise --limit to see them.` means the list was cut. Raise
  `--limit` or narrow with `--category` (each result shows its category;
  `garmin exercise list --help` lists them all).

```json
{
  "name": "Upper A",
  "note": "optional workout notes, max 512 characters",
  "warmup": {"time_s": 300},
  "blocks": [
    {"sets": 3, "steps": [
      {"exercise": "Barbell Bench Press", "reps": 8, "weight_kg": 42.5, "note": "max 200 characters"},
      {"rest": true, "time_s": 90}
    ]},
    {"sets": 2, "steps": [
      {"exercise": "Plank", "time_s": 40},
      {"rest": true}
    ]}
  ],
  "cooldown": {}
}
```

- A block repeats its `steps` `sets` times. `name` and `blocks` are required.
- A step ends after `reps` or `time_s` seconds; with neither, on the lap button.
  Rest, warm-up and cool-down take only `time_s` (and `note`).
- `weight_kg` is kilograms. Give it only when the user named a weight; leave it out
  for body-weight exercises. Pounds are not supported: convert and tell the user.
- `weight_kg` is the one number the watch shows. Per hand or total is the user's
  choice; for dumbbells, write the weight per hand and add "per hand" to the step
  `note`.
- There is no per-side reps field; do not look for one. For "8 per leg", write
  `"reps": 8` and add "per leg" to the step `note`.
- `estimated_duration_min` is an estimate: `time_s` as given, 3 seconds per rep,
  times `sets`; lap-button steps count 0, so a workout without times or reps shows 0.
- An unknown exercise exits 2 with `Did you mean '…'?`. Use that name only when it
  is clearly what the user meant; otherwise search again or ask.

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
  `Use today, yesterday, tomorrow or YYYY-MM-DD.`); correct the call and retry once.

## Privacy

The output is the user's health data. Keep it in this conversation; put it in an
issue, commit, PR or any other external place only when the user asks.
