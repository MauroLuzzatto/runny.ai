# Garmin Workout API Reference

## Step Types (`stepTypeId`)

| ID | Key        | Description                        |
|----|------------|------------------------------------|
| 1  | `warmup`   | Warmup phase                       |
| 2  | `cooldown` | Cooldown phase                     |
| 3  | `interval` | Interval (work phase)              |
| 4  | `recovery` | Recovery (easy jog between intervals) |
| 5  | `rest`     | Rest (full stop)                   |
| 6  | `repeat`   | Repeat group container             |

## End Conditions (`conditionTypeId`)

Defines what ends a step.

| ID | Key          | Value Unit | Description                     |
|----|--------------|------------|---------------------------------|
| 1  | `distance`   | meters     | Step ends after a distance      |
| 1  | `lap.button` | —          | Step ends on manual lap press   |
| 2  | `time`       | seconds    | Step ends after a duration      |
| 3  | `heart.rate` | bpm        | Step ends at a heart rate       |
| 4  | `calories`   | kcal       | Step ends after calories burned |
| 5  | `cadence`    | spm        | Step ends at a cadence          |
| 6  | `power`      | watts      | Step ends at a power output     |
| 7  | `iterations` | count      | Used internally by repeat groups|

## Target Types (`workoutTargetTypeId`)

Defines the target zone for a step.

| ID | Key               | Value Unit   | Description          |
|----|-------------------|--------------|----------------------|
| 1  | `no.target`       | —            | No target            |
| 2  | `heart.rate.zone` | bpm          | Heart rate zone      |
| 3  | `cadence.zone`    | spm          | Cadence zone         |
| 4  | `heart.rate.zone` | bpm          | Heart rate zone (*)  |
| 5  | `power.zone`      | watts        | Power zone           |
| 6  | `pace.zone`       | seconds/km   | Pace zone            |

(*) Note: ID 4 is mapped to heart.rate.zone by Garmin despite the library listing it as speed. Use ID 6 with `pace.zone` for pace targets (values in seconds per km).

## Sport Types (`sportTypeId`)

| ID | Key                  |
|----|----------------------|
| 1  | `running`            |
| 2  | `cycling`            |
| 3  | `swimming`           |
| 4  | `walking`            |
| 5  | `multi_sport`        |
| 6  | `fitness_equipment`  |
| 7  | `hiking`             |
| 8  | `other`              |

## Pace Conversion

Garmin uses **m/s** for speed targets. To convert min/km pace:

| Pace (min/km) | m/s  |
|---------------|------|
| 3:30          | 4.76 |
| 4:00          | 4.17 |
| 4:30          | 3.70 |
| 5:00          | 3.33 |
| 5:30          | 3.03 |
| 6:00          | 2.78 |

Formula: `m/s = 1000 / (minutes * 60 + seconds)`
