# Garmin Connect API — Data Reference

Documents all data fetched from the Garmin Connect API and how it maps to the app's models.

---

## Activity List (`get_activities`)

Endpoint: `/activitylist-service/activities/`

Each activity in the response is parsed into the `Activity` Pydantic model (`core/models.py`).

### Identity & Classification

| API Field | Model Field | Type | Description |
|-----------|-------------|------|-------------|
| `activityId` | `activity_id` | int | Unique activity ID (used internally to fetch splits) |
| `activityName` | `activity_name` | str \| None | Auto-generated or user-set name (e.g. "Interval Running", "Easy Run", "Morning Run") |
| `startTimeLocal` | `start_time_local` | datetime | Local start time |
| `activityType` | `activity_type` | ActivityType | Nested: `typeId`, `typeKey` (e.g. "running"), `parentTypeId` |
| `eventType` | `event_type` | EventType \| None | Nested: `typeId`, `typeKey` (e.g. "training", "race", "fitness") |
| `sportTypeId` | `sport_type_id` | int | 1=running, 2=cycling, 3=swimming, etc. |

### Distance & Duration

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `distance` | `distance` | meters | Total distance |
| `duration` | `duration` | seconds | Active duration |
| `elapsedDuration` | `elapsed_duration` | seconds | Total elapsed time (incl. pauses) |
| `movingDuration` | `moving_duration` | seconds | Time spent moving |

### Speed

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `averageSpeed` | `average_speed` | m/s | Average speed |
| `maxSpeed` | `max_speed` | m/s | Maximum speed |

### Elevation

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `elevationGain` | `elevation_gain` | meters | Total ascent |
| `elevationLoss` | `elevation_loss` | meters | Total descent |
| `minElevation` | `min_elevation` | meters | Lowest point |
| `maxElevation` | `max_elevation` | meters | Highest point |

### Heart Rate

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `averageHR` | `average_hr` | bpm | Average heart rate |
| `maxHR` | `max_hr` | bpm | Maximum heart rate |
| `hrTimeInZone_1` | `hr_zone_1` | seconds | Time in HR zone 1 |
| `hrTimeInZone_2` | `hr_zone_2` | seconds | Time in HR zone 2 |
| `hrTimeInZone_3` | `hr_zone_3` | seconds | Time in HR zone 3 |
| `hrTimeInZone_4` | `hr_zone_4` | seconds | Time in HR zone 4 |
| `hrTimeInZone_5` | `hr_zone_5` | seconds | Time in HR zone 5 |

### Calories

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `calories` | `calories` | kcal | Active calories |
| `bmrCalories` | `bmr_calories` | kcal | Basal metabolic calories |

### Training Effect

| API Field | Model Field | Type | Description |
|-----------|-------------|------|-------------|
| `aerobicTrainingEffect` | `aerobic_training_effect` | float (1.0–5.0) | Garmin aerobic TE score |
| `anaerobicTrainingEffect` | `anaerobic_training_effect` | float (1.0–5.0) | Garmin anaerobic TE score |
| `trainingEffectLabel` | `training_effect_label` | str | e.g. "RECOVERY", "BASE", "TEMPO", "THRESHOLD", "VO2MAX" |
| `activityTrainingLoad` | `activity_training_load` | float | EPOC-based training load |
| `vO2MaxValue` | `vo2_max` | float | VO2max estimate from this activity |

### Power (Running Power)

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `avgPower` | `avg_power` | watts | Average running power |
| `maxPower` | `max_power` | watts | Maximum running power |
| `normPower` | `norm_power` | watts | Normalized power |

### Running Dynamics

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `averageRunningCadenceInStepsPerMinute` | `avg_cadence` | spm | Average cadence |
| `maxRunningCadenceInStepsPerMinute` | `max_cadence` | spm | Max cadence |
| `avgStrideLength` | `avg_stride_length` | cm | Average stride length |
| `avgVerticalOscillation` | `avg_vertical_oscillation` | cm | Average vertical oscillation |
| `avgGroundContactTime` | `avg_ground_contact_time` | ms | Average ground contact time |
| `avgVerticalRatio` | `avg_vertical_ratio` | % | Vertical oscillation / stride length |
| `avgGradeAdjustedSpeed` | `avg_grade_adjusted_speed` | m/s | Grade-adjusted pace |
| `steps` | `steps` | count | Total steps |

### Swimming

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `averageSwimCadenceInStrokesPerMinute` | `avg_swim_cadence` | strokes/min | Average swim cadence |
| `averageSwolf` | `avg_swolf` | — | SWOLF efficiency score |
| `activeLengths` | `active_lengths` | count | Pool lengths swum |
| `strokes` | `strokes` | count | Total strokes |
| `poolLength` | `pool_length` | meters | Pool length |

### Fastest Splits

| API Field | Model Field | Unit | Description |
|-----------|-------------|------|-------------|
| `fastestSplit_1000` | `fastest_1k` | seconds | Fastest 1 km split |
| `fastestSplit_1609` | `fastest_mile` | seconds | Fastest mile split |
| `fastestSplit_5000` | `fastest_5k` | seconds | Fastest 5 km split |
| `fastestSplit_100` | `fastest_100m` | seconds | Fastest 100m (swim) |
| `fastestSplit_400` | `fastest_400m` | seconds | Fastest 400m (swim) |

### Intensity & Meta

| API Field | Model Field | Type | Description |
|-----------|-------------|------|-------------|
| `moderateIntensityMinutes` | `moderate_intensity_minutes` | int | Minutes in moderate intensity |
| `vigorousIntensityMinutes` | `vigorous_intensity_minutes` | int | Minutes in vigorous intensity |
| `differenceBodyBattery` | `difference_body_battery` | int | Body battery change from this activity |
| `lapCount` | `lap_count` | int | Number of laps (>1 suggests intervals) |
| `pr` | `pr` | bool | Personal record achieved |

### Computed Properties

These are derived from the raw fields, not fetched from the API:

| Property | Type | Formula |
|----------|------|---------|
| `sport` | str | `activity_type.type_key` |
| `distance_km` | float | `distance / 1000` |
| `duration_min` | float | `duration / 60` |
| `pace_min_per_km` | float | `(duration / 60) / (distance / 1000)` |

---

## Per-Lap Splits (`get_activity_split_summaries`)

Fetched separately for runs with `lap_count > 1`. Stored in `Activity.splits` as a list of dicts.

| Field | Type | Description |
|-------|------|-------------|
| `distance_m` | int | Lap distance in meters |
| `duration_s` | int | Lap duration in seconds |
| `pace_min_km` | float | Calculated pace (min/km) |
| `avg_hr` | int | Average heart rate for the lap |
| `max_hr` | int | Maximum heart rate for the lap |

Laps with `splitType` of "TOTAL" or "SUMMARY" are excluded.

---

## User Profile (`fetch_user_profile`)

Aggregated from multiple Garmin endpoints into the `UserProfile` model.

### Physical

| Source Endpoint | Model Field | Type | Description |
|-----------------|-------------|------|-------------|
| `get_user_profile` → `userData.weight` | `weight_kg` | float | Body weight (API returns grams, converted to kg) |
| `get_heart_rates` | `resting_hr` | int | Resting heart rate (bpm) |
| Estimated: `220 - age` | `max_hr` | int | Max heart rate (from birth year) |
| Derived from `max_hr` | `hr_zones` | list[dict] | Z1–Z5 at 50–60–70–80–90–100% of max HR |

### Fitness Metrics

| Source Endpoint | Model Field | Type | Description |
|-----------------|-------------|------|-------------|
| `get_user_profile` → `userData.vo2MaxRunning` | `vo2_max` | float | VO2max (may be overridden by training status) |
| `get_training_status` → `mostRecentVO2Max.generic.vo2MaxPreciseValue` | `vo2_max` | float | Precise VO2max (preferred) |
| `get_training_status` → `mostRecentTrainingLoadBalance` | `training_load_7d` | float | Sum of aerobic low + high + anaerobic monthly load |
| `get_training_status` → `mostRecentTrainingStatus.latestTrainingStatusData` | `training_status` | str | e.g. "PRODUCTIVE", "MAINTAINING", "RECOVERY" |
| `get_training_readiness` | `training_readiness` | float | Readiness score (0–100) |
| `get_lactate_threshold` → `speed_and_heart_rate.heartRate` | `lactate_threshold_hr` | int | Lactate threshold heart rate (bpm) |

### Race Predictions

| Source Endpoint | Model Field | Type | Description |
|-----------------|-------------|------|-------------|
| `get_race_predictions` → `time5K` | `race_predictions["5k"]` | float (seconds) | Predicted 5K time |
| `get_race_predictions` → `time10K` | `race_predictions["10k"]` | float (seconds) | Predicted 10K time |
| `get_race_predictions` → `timeHalfMarathon` | `race_predictions["half_marathon"]` | float (seconds) | Predicted half marathon time |
| `get_race_predictions` → `timeMarathon` | `race_predictions["marathon"]` | float (seconds) | Predicted marathon time |

---

## Fields Intentionally Excluded

These fields are available from the API but excluded for privacy or relevance reasons:

- **GPS data** — coordinates, polyline, location names
- **Device info** — device ID, manufacturer, product display name
- **Personal identifiers** — user display name, profile image URL

---

## Data Sent to the LLM

The `_format_run_summary` function (`core/prompts.py`) selects which fields appear in the system prompt. Per run:

- Date, activity name, event type
- Distance (km), pace (min/km)
- Average HR, aerobic TE, anaerobic TE
- Cadence (spm), stride length (cm), ground contact time (ms), vertical oscillation (cm), vertical ratio (%)
- Per-lap splits (distance, duration, pace, HR) when available
