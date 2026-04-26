from garminconnect import Garmin
from garminconnect.workout import (
    ExecutableStep,
    RunningWorkout,
    WorkoutSegment,
    create_repeat_group,
)


def ms_to_pace(speed_ms: float) -> str:
    """Convert m/s to min:sec/km string."""
    if speed_ms <= 0:
        return "—"
    secs_per_km = 1000 / speed_ms
    mins = int(secs_per_km // 60)
    secs = int(secs_per_km % 60)
    return f"{mins}:{secs:02d}"


def _pace_target(speed_ms: float) -> tuple[dict, float, float, str]:
    """Return (targetType, valueLow, valueHigh, description) for a pace target.

    Garmin pace.zone uses m/s for values (same as speed.zone) but displays
    them as pace (min/km) in the UI. valueLow = slower speed, valueHigh = faster speed.
    Uses a +/- 5% speed range around the target.
    """
    low = round(speed_ms * 0.95, 4)  # slower speed = slower pace
    high = round(speed_ms * 1.05, 4)  # faster speed = faster pace
    target_type = {"workoutTargetTypeId": 6, "workoutTargetTypeKey": "pace.zone"}
    desc = f"Target pace: {ms_to_pace(low)} - {ms_to_pace(high)} /km"
    return target_type, low, high, desc


def _make_step(
    step_order: int,
    step_type_id: int,
    step_type_key: str,
    speed_ms: float,
    hr: tuple[int, int] | None = None,
    duration_seconds: int | None = None,
) -> ExecutableStep:
    """Create a workout step with a pace target and optional HR zone."""
    end_condition = {"conditionTypeId": 2, "conditionTypeKey": "time"}
    end_value = float(duration_seconds or 300)

    target_type, low, high, desc = _pace_target(speed_ms)

    kwargs: dict = {
        "stepOrder": step_order,
        "stepType": {"stepTypeId": step_type_id, "stepTypeKey": step_type_key},
        "endCondition": end_condition,
        "targetType": target_type,
        "targetValueOne": low,
        "targetValueTwo": high,
        "description": desc,
    }
    if end_value is not None:
        kwargs["endConditionValue"] = end_value

    # Secondary target: heart rate zone
    if hr:
        kwargs["secondaryTargetType"] = {
            "workoutTargetTypeId": 4,
            "workoutTargetTypeKey": "heart.rate.zone",
        }
        kwargs["secondaryTargetValueOne"] = float(hr[0])
        kwargs["secondaryTargetValueTwo"] = float(hr[1])
        zone = _hr_zone_label(hr)
        kwargs["description"] = f"{desc} | HR {hr[0]}-{hr[1]} bpm ({zone})"

    return ExecutableStep(**kwargs)


def _hr_zone_label(hr: tuple[int, int]) -> str:
    """Estimate the HR zone name from the midpoint of the HR range.

    Uses standard zone definitions based on % of typical max HR (~185-190).
    """
    mid = (hr[0] + hr[1]) / 2
    if mid < 120:
        return "Z1 Recovery"
    if mid < 140:
        return "Z2 Easy"
    if mid < 155:
        return "Z3 Tempo"
    if mid < 170:
        return "Z4 Threshold"
    return "Z5 VO2max"


def build_simple_interval_workout(
    name: str = "5x4min Intervals",
    intervals: int = 5,
    interval_seconds: int = 240,
    recovery_seconds: int = 90,
    warmup_seconds: int = 600,
    cooldown_seconds: int = 300,
    warmup_speed_ms: float = 2.56,
    interval_speed_ms: float = 3.33,
    recovery_speed_ms: float = 2.56,
    cooldown_speed_ms: float = 2.56,
    warmup_hr: tuple[int, int] | None = None,
    interval_hr: tuple[int, int] | None = None,
    recovery_hr: tuple[int, int] | None = None,
    cooldown_hr: tuple[int, int] | None = None,
) -> RunningWorkout:
    """Build a time-based interval workout with pace and HR targets on every step."""
    warmup = _make_step(
        1, 1, "warmup", warmup_speed_ms, hr=warmup_hr, duration_seconds=warmup_seconds
    )
    interval = _make_step(
        1,
        3,
        "interval",
        interval_speed_ms,
        hr=interval_hr,
        duration_seconds=interval_seconds,
    )

    has_recovery = recovery_seconds > 0
    if has_recovery:
        recovery = _make_step(
            2,
            4,
            "recovery",
            recovery_speed_ms,
            hr=recovery_hr,
            duration_seconds=recovery_seconds,
        )
        repeat = create_repeat_group(
            iterations=intervals, workout_steps=[interval, recovery], step_order=2
        )
        recovery_desc = f" ({recovery_seconds}s @ {ms_to_pace(recovery_speed_ms)}/km)"
        total = (
            warmup_seconds
            + intervals * (interval_seconds + recovery_seconds)
            + cooldown_seconds
        )
    else:
        repeat = create_repeat_group(
            iterations=intervals, workout_steps=[interval], step_order=2
        )
        recovery_desc = ""
        total = warmup_seconds + intervals * interval_seconds + cooldown_seconds

    cooldown = _make_step(
        3,
        2,
        "cooldown",
        cooldown_speed_ms,
        hr=cooldown_hr,
        duration_seconds=cooldown_seconds,
    )

    description = (
        f"Warmup: {warmup_seconds // 60}min @ {ms_to_pace(warmup_speed_ms)}/km | "
        f"Main: {intervals}x {interval_seconds // 60}min @ {ms_to_pace(interval_speed_ms)}/km"
        f"{recovery_desc} | "
        f"Cooldown: {cooldown_seconds // 60}min @ {ms_to_pace(cooldown_speed_ms)}/km"
    )

    return RunningWorkout(
        workoutName=name,
        description=description,
        estimatedDurationInSecs=total,
        workoutSegments=[
            WorkoutSegment(
                segmentOrder=1,
                sportType={"sportTypeId": 1, "sportTypeKey": "running"},
                workoutSteps=[warmup, repeat, cooldown],
            )
        ],
    )


def build_steady_run(
    name: str = "Easy Run",
    run_seconds: int = 3000,
    warmup_seconds: int = 600,
    cooldown_seconds: int = 300,
    run_speed_ms: float = 3.03,
    warmup_speed_ms: float = 2.56,
    cooldown_speed_ms: float = 2.56,
    run_hr: tuple[int, int] | None = None,
    warmup_hr: tuple[int, int] | None = None,
    cooldown_hr: tuple[int, int] | None = None,
) -> RunningWorkout:
    """Build a steady-pace run: warmup → main time block → cooldown. All steps are time-based."""
    warmup = _make_step(
        1, 1, "warmup", warmup_speed_ms, hr=warmup_hr, duration_seconds=warmup_seconds
    )
    main_run = _make_step(
        2, 3, "interval", run_speed_ms, hr=run_hr, duration_seconds=run_seconds
    )
    cooldown = _make_step(
        3,
        2,
        "cooldown",
        cooldown_speed_ms,
        hr=cooldown_hr,
        duration_seconds=cooldown_seconds,
    )

    total = warmup_seconds + run_seconds + cooldown_seconds

    description = (
        f"Warmup: {warmup_seconds // 60}min @ {ms_to_pace(warmup_speed_ms)}/km | "
        f"Run: {run_seconds // 60}min @ {ms_to_pace(run_speed_ms)}/km | "
        f"Cooldown: {cooldown_seconds // 60}min @ {ms_to_pace(cooldown_speed_ms)}/km"
    )

    return RunningWorkout(
        workoutName=name,
        description=description,
        estimatedDurationInSecs=total,
        workoutSegments=[
            WorkoutSegment(
                segmentOrder=1,
                sportType={"sportTypeId": 1, "sportTypeKey": "running"},
                workoutSteps=[warmup, main_run, cooldown],
            )
        ],
    )


def upload_workout(client: Garmin, workout: RunningWorkout) -> dict:
    """Upload a running workout to Garmin Connect."""
    return client.upload_running_workout(workout)


def schedule_workout(client: Garmin, workout_id: int, date: str) -> dict:
    """Schedule an uploaded workout on the Garmin calendar."""
    url = f"{client.garmin_workouts_schedule_url}/{workout_id}"
    return client.garth.post("connectapi", url, json={"date": date}, api=True).json()
