# garmin-cli

`garmin` reads your Garmin Connect data and prints it as JSON. It can also log a
weigh-in, adjust a night's sleep times, manage workouts, save GPX files as
courses, send a course to a watch, and read, create, edit, delete and send PacePro plans. Scripts, agents and people at a terminal can use it. It wraps
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

`garmin login` asks for an MFA code if your account has one. It always logs in as
`GARMIN_EMAIL`, even when a saved login exists, and then saves the tokens to
`~/.garminconnect`, or to the path in `GARMINTOKENS` if you set it. A failed login
keeps the saved tokens. The other commands read those tokens. When the tokens expire,
a command fails and tells you to run `garmin login` again.

| Message starts with | Fix |
|---|---|
| `Not logged in` | Run `garmin login`. |
| `GARMIN_EMAIL is not set` | `export GARMIN_EMAIL=you@example.com` |
| `No Keychain password` | Add it with the `security add-generic-password` line above. |
| `'garmin login' reads the password from the macOS Keychain` | Log in on a Mac and copy the token folder, or point `GARMINTOKENS` at a copy. With `GARMINTOKENS` set, the message says to copy a token folder from a Mac and point `GARMINTOKENS` at it. |
| `Garmin rejected the login` | Fix the Keychain password, then run `garmin login`. |
| `No MFA code entered` | Run `garmin login` in a terminal and type the code. |
| `Garmin is rate-limiting logins` | Wait about an hour, then run `garmin login`. |
| `GARMINTOKENS holds the token JSON itself` | Set `GARMINTOKENS` to a token folder path, or unset it, then run `garmin login`. |

## Dates

Every date argument takes `today`, `yesterday`, `tomorrow` or `YYYY-MM-DD`.

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

### recovery view

```sh
garmin recovery view              # today
garmin recovery view yesterday
garmin recovery view 2026-07-05
```

```json
{
  "date": "2026-07-05",
  "recovery_time_h": 12.5,
  "readiness": {
    "score": 62,
    "level": "MODERATE",
    "feedback": "RECOVERING",
    "factors": {
      "sleep": {"pct": 80, "feedback": "GOOD"},
      "recovery_time": {"pct": 40, "feedback": "MODERATE"},
      "hrv": {"pct": 70, "feedback": "GOOD"},
      "acute_load": {"pct": 90, "feedback": "VERY_GOOD"},
      "sleep_history": {"pct": 60, "feedback": "MODERATE"},
      "stress_history": {"pct": 85, "feedback": "GOOD"}
    }
  },
  "training_status": {
    "status": "PRODUCTIVE",
    "since": "2026-07-01",
    "paused": false,
    "acute_load": 400,
    "chronic_load": 380,
    "chronic_load_min": 300.0,
    "chronic_load_max": 500.0,
    "acwr": 1.05,
    "acwr_status": "OPTIMAL",
    "load_focus": "ANAEROBIC_SHORTAGE",
    "monthly_load": {
      "aerobic_low": {"load": 500.0, "target_min": 400, "target_max": 800},
      "aerobic_high": {"load": 600.0, "target_min": 300, "target_max": 700},
      "anaerobic": {"load": 50.0, "target_min": 100, "target_max": 300}
    }
  },
  "hrv": {
    "status": "BALANCED",
    "last_night_ms": 50,
    "weekly_avg_ms": 52,
    "baseline_low_ms": 45,
    "baseline_high_ms": 60
  }
}
```

Garmin's recovery verdict for one day. `readiness` is the newest training readiness
snapshot of the day, with each contributing factor's percentage and feedback.
`recovery_time_h` is the recovery time left, in hours, from the same snapshot.
`training_status` comes from the primary training device: the status without
Garmin's number suffix (`PRODUCTIVE_3` is `PRODUCTIVE`), the acute and chronic
training load and their ratio (`acwr`), Garmin's load focus feedback, and the
monthly load per intensity with its target range. `hrv` is last night's average HRV, the 7-day average, the balanced
baseline range and the status. Garmin's own keys, such as `MODERATE` or `BALANCED`,
are printed as Garmin sends them.

A section Garmin has no data for that day is `null`. Watches without training
readiness, such as the fenix 6, always print `null` for `readiness` and
`recovery_time_h`. A day with no section at all exits with status 1.

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

The times are converted with the night's own offsets from Garmin Connect: the start
with the offset at lights-out, the end with the offset at wake-up.

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

`weight add` logs a manual weigh-in and prints what it logged:
`{"date": "2026-07-05", "time": "07:30:00", "weight": 82.4, "unit": "kg"}`.

```sh
garmin weight add 82.4                           # kg, now
garmin weight add 181.5 --unit lbs
garmin weight add 82.4 --at "2026-07-05 07:30"   # local time
```

`--at` takes only `YYYY-MM-DD HH:MM`, because a weigh-in needs a time.

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
`hr_zones` (seconds spent in each zone and the zone's lower bound in bpm). An ID that
is not a whole number of 1 or more exits with status 2 before logging in:
`garmin: Invalid activity ID 'abc'. Run 'garmin activities' to list IDs.`

### activity add

```sh
garmin activity add --type strength_training --start "2026-07-05 18:30" --duration 45
garmin activity add --type running --start "2026-07-05 07:00" --duration 30 --distance 5.2 --name "Park run"
garmin activity add --type walking --start "2026-07-05 12:00" --duration 65 --distance 4.3 --calories 266.7
```

Creates a private manual activity on Garmin Connect, for example a gym session or a
run without a watch, then prints it as `garmin activity` does. `--type` is a Garmin
type key such as `running`, `cycling` or `strength_training`; an unknown key exits
with status 2 and suggests the closest one. `--start` is local
`YYYY-MM-DD HH:MM`, `--duration` whole minutes, and `--distance` kilometers
(default 0). `--calories` sets the kilocalories, a number above 0; without it
Garmin estimates them, often far below its web form's value. `--name` defaults to the type, like `Strength Training`. The time zone
is the machine's, from `TZ` or the `/etc/localtime` link; `--tz Europe/Warsaw`
overrides it, and a machine without one exits with status 2 and asks for `--tz`.

### activity delete

```sh
garmin activity delete 1234567890 --dry-run
garmin activity delete 1234567890
```

Deletes an activity from Garmin Connect, for example a wrong manual entry, without
asking. Take the ID from `garmin activities`. The command first reads the activity,
so an unknown ID fails with the `garmin activity` message and deletes nothing. After
the deletion, stdout is `{"deleted": 1234567890}` and stderr
`garmin: Deleted "Park run" (2026-07-05 07:00).` `--dry-run` only reads the
activity: stdout `{"would_delete": 1234567890}`, stderr
`garmin: Would delete "Park run" (2026-07-05 07:00).` An activity without a name
shows as `activity 1234567890`; without a start time, the time is left out.

### workouts

```sh
garmin workouts                                   # the 20 newest workouts
garmin workouts --limit 200
```

```json
[
  {
    "id": 987654321,
    "name": "Intervals 4x1k",
    "sport": "running",
    "estimated_duration_min": 45.5,
    "created": "2026-07-05T08:00:00.0",
    "updated": "2026-07-06T09:00:00.0"
  }
]
```

The workouts in the Garmin Connect workout library, newest created first.
`--limit` caps the count (default 20). An empty library prints `[]`. A key Garmin
has no value for is left out.

### workout

```sh
garmin workout 987654321
```

```json
{
  "id": 987654321,
  "name": "Intervals 4x1k",
  "sport": "running",
  "estimated_duration_min": 45.5,
  "created": "2026-07-05T08:00:00.0",
  "updated": "2026-07-06T09:00:00.0",
  "steps": [
    {"type": "warmup", "end": "time", "end_value": 600.0, "target": "no.target"},
    {
      "type": "repeat",
      "iterations": 4,
      "steps": [
        {"type": "interval", "end": "distance", "end_value": 1000.0, "target": "pace.zone", "target_low": 3.7, "target_high": 4.0}
      ]
    }
  ]
}
```

One workout by the `id` from `garmin workouts`. It has the same keys as a
`workouts` item, plus `steps`. A step's `end` says when it ends (`time` in
seconds, `distance` in meters, `lap.button`) and `end_value` how much. `target`
is the target type; `target_low` and `target_high` are its limits, for a pace
target in m/s. A repeat step has `iterations` and its own `steps`. A strength step
has `exercise`, the name `garmin exercise list` prints, and, when it has a weight,
`weight` and `weight_unit` (`kilogram`). An exercise missing from garmin-cli's
catalog shows as `CATEGORY/EXERCISE_NAME`.

### workout add

```sh
garmin workout add --file intervals.json
garmin workout add --file intervals.json --schedule 2026-07-06
cat intervals.json | garmin workout add --file -
garmin workout add --strength --file upper.json
```

Saves a structured workout to the Garmin Connect workout library. The file holds
one workout in Garmin's own JSON format, the shape `garmin workout ID --raw` prints;
`skills/garmin/SKILL.md` has a complete example with a warm-up, a repeat group with
a pace target and a cool-down, and lists the step, end condition and target IDs.
Pace targets are in meters per second. `--file -` reads the workout from stdin.
`--schedule DATE` also puts the workout on the calendar, and the watch gets it on
its next sync.

garmin-cli checks only that the input is a JSON object with `workoutName`,
`sportType` and `workoutSegments`, and exits with status 2 otherwise; Garmin checks
the rest. stdout is
`{"id": 1234567890, "name": "5 x 1 km", "estimated_duration_min": 55.0, "scheduled": "2026-07-06"}`
and stderr
`garmin: Created workout "5 x 1 km" (ID 1234567890) and scheduled it for 2026-07-06.`
When the scheduling fails, the workout exists without a calendar entry: the command
exits 1 with `garmin: Created workout "5 x 1 km" (ID 1234567890) but did not schedule it.`
followed by the cause. Running it again creates a second copy.

#### Strength workouts

`--strength` reads a shorter file that describes a strength workout: a warm-up,
blocks of sets with exercise and rest steps, and a cool-down.

```json
{
  "name": "Upper A",
  "note": "Workout notes, up to 512 characters",
  "warmup": {"time_s": 300, "note": "Rower"},
  "blocks": [
    {"sets": 3, "steps": [
      {"exercise": "Barbell Bench Press", "reps": 8, "weight_kg": 42.5, "note": "Pause at the chest"},
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

- `name` and `blocks` are required; `note`, `warmup` and `cooldown` are optional.
- A block repeats its `steps` `sets` times.
- An exercise step names an exercise from `garmin exercise list`. Case, spaces and
  hyphens do not matter (`close grip barbell bench press` works).
- A step ends after `reps` repetitions or `time_s` seconds; with neither, it ends when
  you press the lap button. A rest step is `{"rest": true}` with an optional
  `time_s`. The warm-up and cool-down take `time_s` too.
- `weight_kg` is the weight in kilograms; leave it out for body-weight exercises. It
  is the one number the watch shows for the step. Whether it is per hand or the total
  is your choice; for dumbbells, give the weight per hand and say so in the step
  `note`.
- Garmin has no per-side reps field. For "8 per leg", write `"reps": 8` and say
  "per leg" in the step `note`.
- `note` on a step is shown on the watch, up to 200 characters.
- garmin-cli sends an estimated duration with the workout: `time_s` as given, 3
  seconds per rep, each block times its `sets`, and nothing for a step that ends on
  the lap button. The example above is 722 seconds. When Garmin answers 0, the
  `estimated_duration_min` that `workout add` prints is this estimate.

garmin-cli checks the whole file before it logs in: an unknown key, an unknown
exercise or a bad number exits with status 2 and names the step, for example
`garmin: Step 1 of block 1 in 'upper.json' has an unknown exercise 'barbel bench press'. Did you mean 'Barbell Bench Press'? Find names with 'garmin exercise list --search TEXT'.`
Pounds, calorie and heart-rate end conditions, and Garmin's benchmark weights are
not supported. Output, `--schedule` and errors are the same as for any other
`workout add`.

### workout edit

```sh
garmin workout 1234567890 --raw > intervals.json
# change intervals.json
garmin workout edit 1234567890 --file intervals.json
garmin workout edit 1234567890 --strength --file upper.json
```

Replaces a workout in the Garmin Connect workout library with the workout in the
file. The workout keeps its ID, so its calendar entries stay. Garmin replaces the
whole workout, so start from the `garmin workout ID --raw` output and change only
what you need. `--file -` reads the workout from stdin. The input check is the same
as for `workout add`, and the command reads the workout first, so an unknown ID
fails with the `garmin workout` message and changes nothing. stdout is the updated
workout in the `garmin workout` format and stderr
`garmin: Updated workout "5 x 1 km" (ID 1234567890).`

`--strength` rebuilds the workout from a file in the short format of
`workout add --strength` (see "Strength workouts" above), so changing an exercise
needs no raw JSON. The file describes the whole workout, and the input check is the
same as for `workout add --strength`.

### workout delete

```sh
garmin workout delete 1234567890 --dry-run
garmin workout delete 1234567890
```

Deletes a workout from the Garmin Connect workout library without asking. Take the
ID from `garmin workouts` or from the output of `garmin workout add`. Garmin also
removes the workout's calendar entries. The command first reads the workout, so an
unknown ID fails with the `garmin workout` message and deletes nothing. After the
deletion, stdout is `{"deleted": 1234567890}` and stderr
`garmin: Deleted "5 x 1 km".` `--dry-run` only reads the workout: stdout
`{"would_delete": 1234567890}`, stderr `garmin: Would delete "5 x 1 km".` A workout
without a name shows as `workout 1234567890`.

### workout schedule

```sh
garmin workout schedule 987654321 tomorrow
garmin workout schedule 987654321 2026-07-06
```

Puts a workout from the workout library on the Garmin Connect calendar; the watch
gets it on its next sync. stdout is
`{"schedule_id": 123456789, "date": "2026-07-06", "workout_id": 987654321, "name": "Intervals 4x1k"}`
and stderr `garmin: Scheduled workout "Intervals 4x1k" (ID 987654321) for 2026-07-06.`
An unknown workout ID exits 1 before anything is scheduled.

### workout unschedule

```sh
garmin workout unschedule 123456789
```

Takes one entry off the calendar by the `schedule_id` from `garmin workout calendar`.
The workout stays in the workout library. stdout is `{"unscheduled": 123456789}` and
stderr `garmin: Removed calendar entry 123456789.`

### workout calendar

```sh
garmin workout calendar                                  # today to 4 weeks after today
garmin workout calendar --from 2026-07-01                # 2026-07-01 to 2026-07-29
garmin workout calendar --from 2026-07-01 --to 2026-07-31
```

```json
[
  {
    "schedule_id": 123456789,
    "date": "2026-07-06",
    "workout_id": 987654321,
    "name": "Intervals 4x1k"
  }
]
```

The workouts on the Garmin Connect calendar between `--from` and `--to`, both
included, oldest first. `--from` defaults to today and `--to` to 4 weeks after
`--from`; a `--to` before `--from` exits with status 2. Other calendar items, such as
activities, are left out. An empty range prints `[]`.

### exercise list

```sh
garmin exercise list --search "split squat"
garmin exercise list --search press --limit 100
garmin exercise list --category CALF_RAISE --search seated
```

```json
[
  {"name": "Barbell Bulgarian Split Squat", "category": "LUNGE"},
  {"name": "Dumbbell Bulgarian Split Squat", "category": "LUNGE"}
]
```

Exercises from the Garmin Connect strength exercise catalog, sorted by name. A
`name` goes in the `exercise` key of a strength workout file. `--search` keeps the
names that contain every word, in any order, ignoring case, punctuation and the
spaces between words, so `pushup` finds `Push-up`. A word can be part of a longer
one (`raise` finds `Banded Calf Raises`). When no name has every word, the command
prints the closest names instead, closest first, with the stderr line
`garmin: No exercise has every word of 'step down'. Showing the closest names; search again if none fits.`
With no close name either, it prints `[]`.

`--category` keeps one category, in any case; `garmin exercise list --help` lists the
categories, and an unknown one exits with status 2. `--limit` caps the count
(default 20); when it cuts the list, stderr says how many more match, for example
`garmin: 15 more exercises match. Raise --limit to see them.` The catalog comes with
the garminconnect library, so the command needs no login and makes no network call.

### course create

```sh
garmin course create --file hills.gpx --name "Hill repeats" --type trail_running
garmin course create --file hills.gpx                       # running, private
cat hills.gpx | garmin course create --file - --name "Hill repeats"
```

Saves a GPX file as a course in Garmin Connect, in two Garmin steps. The import
step sends the file to Garmin, which parses it into a course object; that object
is temporary, has no ID, and nothing is saved yet. The create step saves it as a
course with its own ID, the one `garmin course view` takes. Garmin rejects the
import object as a save body, so the create step sends only the course fields
Garmin saves, leaves out the empty ones, and fills in the start point (the first
track point), the coordinate system (WGS84) and the source type (GPX) when the
import left them empty. Garmin computes distance and elevation on save. When the
import finds no track, the command exits 1 and saves nothing.

`--name` sets the course name (default: the name Garmin reads from the GPX, else
the file name without `.gpx`, or `Course` for stdin). `--type` takes a Garmin
activity type key, as `garmin activity add` does (default `running`); an unknown
key exits 2 before the import. `--privacy` is `private` (default) or `public`.
`--file -` reads the GPX from stdin.

garmin-cli checks before it calls Garmin that the file is readable XML with a
`<gpx>` root and at least 2 track or route points (`trkpt` or `rtept`), and exits
2 otherwise. TCX and FIT files are not supported. stdout is the saved course, with
the keys of `garmin course view`, and stderr
`garmin: Imported 'hills.gpx' and saved it as course "Hill repeats" (ID 1234567).`
Running it again saves a second copy. `garmin course send` sends the course to
a watch.

### course list

```sh
garmin course list
garmin course list --limit 100
```

```json
[
  {
    "id": 1234567,
    "name": "Hill repeats",
    "type": "trail_running",
    "distance_m": 5321.5,
    "elevation_gain_m": 210.25,
    "elevation_loss_m": 209.75,
    "privacy": "private"
  }
]
```

The courses saved in Garmin Connect, in the order Garmin returns them. `--limit`
caps the count (default 20). No courses prints `[]`. A key Garmin has no value for
is left out.

### course view

```sh
garmin course view 1234567
```

One course by the `id` from `garmin course list` or `garmin course create`, with
the same keys as a `course list` item. `distance_m` and the elevation keys are
meters; Garmin computes them when it saves the course.

### course send

```sh
garmin device list                         # find the watch's id
garmin course send 1234567 --device 3333333333
```

```json
{
  "course_id": 1234567,
  "course": "Hill repeats",
  "device_id": 3333333333,
  "device": "My watch",
  "message_id": 888888
}
```

Queues a saved course for one device, like *Send to Device* in Garmin Connect.
The watch downloads it on its next sync with Garmin Connect. A success means
Garmin accepted the message, not that the course is on the watch yet.

The course ID comes from `garmin course list`, and `--device` takes an `id` from
`garmin device list`; there is no default device. The command fetches the course
and the account's devices first and exits 1, sending nothing, when either ID is
unknown. stderr is
`garmin: Queued course "Hill repeats" (ID 1234567) for device "My watch" (ID 3333333333). The watch gets it on its next sync.`
`message_id` is left out when Garmin's answer has none. `--raw` prints Garmin's
answer to the send. Running it again queues the course again.

garminconnect has no call for this, so garmin-cli posts the device message
itself, through the library's HTTP client and the same endpoint the library's
`push_workout_to_device` uses for workouts. The course fields follow
[bpauli/gccli](https://github.com/bpauli/gccli) (`internal/garminapi/courses.go`,
`SendCourseToDevice`). If Garmin changes the message format, the command fails
with `Garmin Connect rejected the request`.

### pacepro list

```sh
garmin pacepro list
garmin pacepro list --limit 50
```

```json
[
  {
    "id": 7654321,
    "name": "Hill repeats 10k",
    "course_id": 1234567,
    "split": "elevation",
    "distance_m": 10000.0,
    "goal_time_s": 4000,
    "goal_pace_s_per_km": 400,
    "pacing_strategy": -0.25,
    "uphill_effort": 1.5,
    "splits": 12
  }
]
```

The PacePro plans saved in Garmin Connect, in the order Garmin returns them.
`--limit` caps the count (default 20). No plans prints `[]`. A key Garmin has no
value for is left out.

- `course_id` is the course the plan was made from; `garmin course view` takes it.
- `split` is `km` or `elevation`, the split modes seen on a real account. Any other
  value Garmin sends (for example miles) is printed unchanged.
- `goal_pace_s_per_km` comes from Garmin's goal speed; `splits` is the number of splits.
- `pacing_strategy` and `uphill_effort` are Garmin's slider values, printed unchanged.
  Garmin does not document their scale or which sign means a negative split.

### pacepro view

```sh
garmin pacepro view 7654321
```

```json
{
  "id": 7654321,
  "name": "Hill repeats 10k",
  "split": "elevation",
  "splits": [
    {
      "distance_m": 4000.0,
      "pace_s_per_km": 417,
      "elevation_change_m": 30.5,
      "cumulative_distance_m": 4000.0,
      "cumulative_time_s": 1666.67
    }
  ]
}
```

One plan by the `id` from `garmin pacepro list`, with the `pacepro list` keys and
its splits in order: each split's length, target pace, elevation change from start
to end, and the distance and time from the start at its end. An unknown ID exits 1.

garminconnect 0.3.20 has one PacePro call, `get_pace_bands()`, and no call to
create, edit, delete or send a plan. `pacepro view`, `pacepro create`,
`pacepro edit`, `pacepro delete` and `pacepro send` send the Garmin Connect
website's own requests through the library's HTTP client. Change a plan's split
type, sliders or single paces in Garmin Connect: Training & Planning → PacePro
Pacing Strategies.

### pacepro create

```sh
garmin pacepro create --course 1234567 --goal-time 1:00:00 --dry-run
garmin pacepro create --course 1234567 --goal-pace 5:45 --name "Hill race"
```

Computes a PacePro plan from a saved course and saves it to Garmin Connect. stdout
is the saved plan with the keys of `garmin pacepro view`, and stderr
`garmin: Created PacePro plan 7654321 from course 1234567.` Each run saves a new
plan. `--dry-run` prints the plan it would save and saves nothing.

- `--course` takes an `id` from `garmin course list`. An unknown ID, or a course
  without a GPS track with elevation, exits 1 before anything is saved.
- Give exactly one of `--goal-time H:MM:SS` and `--goal-pace M:SS` (per km).
  The goal pace is turned into a goal time over the course distance.
- `--name` names the plan (default: the course name).

The plan has a split every km and the website's default sliders (uphill effort 0,
pacing strategy 0). Elevation splits, miles and other slider values are not
supported; make those plans on the website.

The Garmin Connect website computes every split's target pace in the browser and
sends the finished plan; Garmin's servers only store it. garmin-cli computes the
splits with its own algorithm (`src/garmin_cli/pacing.py`, see
[ADR 0001](docs/adr/0001-pacepro-clean-room-algorithm.md)), tuned against plans
saved on the website with the default sliders: ten plans on courses from 5 to
55 km, flat to hilly, with grades per km from −11 % to +13 %. On nine of them every
split is within 3 s/km of the website's, and on the tenth within 3.4 s/km. The
model:

- Each split runs at the goal pace times
  `1 + 1.68 × grade + 2.5 × grade²` on a climb and
  `1 + 1.68 × grade + 10 × grade²` on a descent, where grade is the split's
  elevation change over its length. All splits, the last one included, are then
  scaled to finish in the goal time.
- Near flat, 1 % of grade makes a split about 1.7 % slower uphill or faster
  downhill. Climbs cost a little more as they steepen. On descents the gain peaks
  at about −8 % (7 % faster than flat) and is gone by about −17 %.
- The splits end at the track's great-circle length, which is a little shorter
  than the course distance Garmin shows, as on the website. Each split's grade is
  measured along that length.

### pacepro edit

```sh
garmin pacepro edit 7654321 --name "Hill race"
garmin pacepro edit 7654321 --goal-time 0:58:00
garmin pacepro edit 7654321 --goal-pace 5:40 --name "Hill race"
```

Changes a saved PacePro plan's name, goal or both, and keeps its ID. Give at least
one of `--name`, `--goal-time H:MM:SS` and `--goal-pace M:SS` (per km); with none,
or with both goals, it exits 2. The command first reads the plan, so an unknown ID
fails with the `garmin pacepro view` message and changes nothing. stdout is the
stored plan with the keys of `garmin pacepro view`, and stderr
`garmin: Updated PacePro plan "Hill race".`

- A new name alone keeps the plan's splits and settings.
- A new goal recomputes every split from the plan's course with the same algorithm
  as `pacepro create`, so the course needs a GPS track with elevation. A goal pace
  is turned into a goal time over the course distance. The plan is then saved with
  km splits and the default sliders, even when it had elevation splits, other
  slider values or paces edited by hand on the website. When it had any of those,
  stderr says so: `garmin: Updated PacePro plan "Hill race"; it now has km splits
  at the default sliders.`

### pacepro delete

```sh
garmin pacepro delete 7654321 --dry-run
garmin pacepro delete 7654321
```

Deletes a PacePro plan from Garmin Connect without asking. Take the ID from
`garmin pacepro list`. The command first reads the plan, so an unknown ID fails with
the `garmin pacepro view` message and deletes nothing. After the deletion, stdout is
`{"deleted": 7654321}` and stderr `garmin: Deleted PacePro plan "Hill repeats 10k".`
`--dry-run` only reads the plan: stdout `{"would_delete": 7654321}`, stderr
`garmin: Would delete PacePro plan "Hill repeats 10k".` A plan without a name shows
as `PacePro plan 7654321`.

### pacepro send

```sh
garmin device list                         # find the watch's id
garmin pacepro send 7654321 --device 3333333333
```

```json
{
  "plan_id": 7654321,
  "plan": "Hill repeats 10k",
  "device_id": 3333333333,
  "device": "My watch"
}
```

Queues a PacePro plan for one device, like *Send to Device* in Garmin Connect. The
watch downloads it on its next sync with Garmin Connect. A success means Garmin
accepted the plan, not that it is on the watch yet.

The plan ID comes from `garmin pacepro list`, and `--device` takes an `id` from
`garmin device list`; there is no default device. The command fetches the plan and
the account's devices first and exits 1, sending nothing, when either ID is
unknown. stderr is
`garmin: Queued PacePro plan "Hill repeats 10k" (ID 7654321) for device "My watch" (ID 3333333333). The watch gets it on its next sync.`
A plan without a name shows as `PacePro plan 7654321`, and a key with no value is
left out of stdout. `--raw` prints Garmin's answer to the send, which is `{}`
because Garmin answers with no body. Running it again queues the plan again.

The command sends only the plan. The watch runs a PacePro plan with its course, so
the course has to reach the watch too: if it does not arrive with the plan, send it
with `garmin course send` and the plan's `course_id`.

garminconnect has no call for this, so garmin-cli sends the website's own request
through the library's HTTP client. If Garmin changes it, the command fails with
`Garmin Connect rejected the request`.

### device list

```sh
garmin device list
```

```json
[
  {
    "id": 3333333333,
    "name": "My watch",
    "model": "fēnix 6 Pro"
  }
]
```

The devices registered to the Garmin Connect account. `id` is what
`garmin course send --device` and `garmin pacepro send --device` take, `name` is the device's name in Garmin Connect,
and `model` its product name. A key Garmin has no value for is left out. No
devices prints `[]`.

## Raw output

`stats`, `recovery view`, `sleep`, `weight`, `bp`, `activities`, `activity`,
`workouts`, `workout`, `workout calendar`, `course list`, `course view`,
`course send`, `pacepro send` and `device list` accept `--raw`. It
prints the full Garmin response instead of the summary. `activity --raw` combines
three responses under `summary`, `splits` and `hr_zones`, and `recovery view --raw`
under `training_readiness`, `training_status` and `hrv`. `workout calendar --raw`
prints Garmin's calendar items for the workouts in the range, without the other
item types. `stats --raw` and
`recovery view --raw` skip the not-synced check.

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
| `recovery view` day not synced | `garmin: No recovery data for <date> yet. Sync your watch with Garmin Connect, then try again.` |
| `sleep` night not synced | `garmin: No sleep data for the night ending <date> yet. Sync your watch with Garmin Connect, or use --night-of if <date> is the night you went to bed.` |
| `sleep --night-of` night not synced | `garmin: No sleep data for the night of <date> yet. Sync your watch with Garmin Connect, then try again.` |
| `sleep set` night has no time zone | `garmin: Garmin Connect sent no time zone for the night ending <date>, so garmin-cli cannot convert the times. Adjust the sleep times in the Garmin Connect app.` |
| `activity <id>` not found | `garmin: No activity with ID <id>. Run 'garmin activities' to list recent IDs.` |
| `workout <id>`, `workout edit <id>` or `workout schedule <id>` not found | `garmin: No workout with ID <id>. Run 'garmin workouts' to list IDs.` |
| `course view <id>` not found | `garmin: No course with ID <id>. Run 'garmin course list' to list IDs.` |
| `course send <id>` course not found | `garmin: No course with ID <id>. Run 'garmin course list' to list IDs.` |
| `course send --device <id>` device not found | `garmin: No device with ID <id>. Run 'garmin device list' to list IDs.` |
| `pacepro create --course <id>` course not found | `garmin: No course with ID <id>. Run 'garmin course list' to list IDs.` |
| `pacepro create` course without a track | `garmin: Course <id> has no track with elevation, which PacePro needs. Pick another course from 'garmin course list'.` |
| `pacepro edit <id>` plan not found | `garmin: No PacePro plan with ID <id>. Run 'garmin pacepro list' to list IDs.` |
| `pacepro send <id>` plan not found | `garmin: No PacePro plan with ID <id>. Run 'garmin pacepro list' to list IDs.` |
| `pacepro send --device <id>` device not found | `garmin: No device with ID <id>. Run 'garmin device list' to list IDs.` |
| `course create` import has no track | `garmin: Garmin found no track in '<file>', so no course was saved. Check that the file imports in Garmin Connect's course import.` |
| `workout unschedule <id>` not found | `garmin: No calendar entry with schedule ID <id>. Run 'garmin workout calendar' to list schedule IDs.` |
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
