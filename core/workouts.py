from garminconnect import Garmin
from garminconnect.workout import (
    ExecutableStep,
    RunningWorkout,
    WorkoutSegment,
    create_warmup_step,
    create_cooldown_step,
    create_interval_step,
    create_recovery_step,
    create_repeat_group,
)


def build_simple_interval_workout(
    name: str = "5x4min Intervals (simple)",
    intervals: int = 5,
    interval_seconds: int = 240,
    recovery_seconds: int = 90,
    warmup_seconds: int = 600,
    cooldown_seconds: int = 300,
) -> RunningWorkout:
    """Build a simple time-based interval workout with no targets."""
    warmup = create_warmup_step(duration_seconds=warmup_seconds, step_order=1)
    interval = create_interval_step(duration_seconds=interval_seconds, step_order=1)
    recovery = create_recovery_step(duration_seconds=recovery_seconds, step_order=2)
    repeat = create_repeat_group(
        iterations=intervals, workout_steps=[interval, recovery], step_order=2
    )
    cooldown = create_cooldown_step(duration_seconds=cooldown_seconds, step_order=3)

    total = warmup_seconds + intervals * (interval_seconds + recovery_seconds) + cooldown_seconds

    return RunningWorkout(
        workoutName=name,
        estimatedDurationInSecs=total,
        workoutSegments=[
            WorkoutSegment(
                segmentOrder=1,
                sportType={"sportTypeId": 1, "sportTypeKey": "running"},
                workoutSteps=[warmup, repeat, cooldown],
            )
        ],
    )


def build_advanced_interval_workout(
    name: str = "5x1km Intervals (with targets)",
    intervals: int = 5,
    interval_distance_m: int = 1000,
    recovery_seconds: int = 90,
    warmup_seconds: int = 600,
) -> RunningWorkout:
    """Build a distance-based interval workout with pace & HR targets."""
    warmup = create_warmup_step(
        duration_seconds=warmup_seconds,
        step_order=1,
        target_type={"workoutTargetTypeId": 2, "workoutTargetTypeKey": "heart.rate.zone"},
    )

    interval_pace = ExecutableStep(
        stepOrder=1,
        stepType={"stepTypeId": 3, "stepTypeKey": "interval"},
        endCondition={"conditionTypeId": 1, "conditionTypeKey": "distance"},
        endConditionValue=interval_distance_m,
        targetType={"workoutTargetTypeId": 4, "workoutTargetTypeKey": "speed.zone"},
    )

    recovery_cadence = ExecutableStep(
        stepOrder=2,
        stepType={"stepTypeId": 4, "stepTypeKey": "recovery"},
        endCondition={"conditionTypeId": 2, "conditionTypeKey": "time"},
        endConditionValue=recovery_seconds,
        targetType={"workoutTargetTypeId": 3, "workoutTargetTypeKey": "cadence.zone"},
    )

    repeat = create_repeat_group(
        iterations=intervals, workout_steps=[interval_pace, recovery_cadence], step_order=2
    )

    cooldown = ExecutableStep(
        stepOrder=3,
        stepType={"stepTypeId": 2, "stepTypeKey": "cooldown"},
        endCondition={"conditionTypeId": 1, "conditionTypeKey": "lap.button"},
    )

    return RunningWorkout(
        workoutName=name,
        estimatedDurationInSecs=warmup_seconds + intervals * (300 + recovery_seconds),
        workoutSegments=[
            WorkoutSegment(
                segmentOrder=1,
                sportType={"sportTypeId": 1, "sportTypeKey": "running"},
                workoutSteps=[warmup, repeat, cooldown],
            )
        ],
    )


def upload_workout(client: Garmin, workout: RunningWorkout) -> dict:
    """Upload a running workout to Garmin Connect."""
    return client.upload_running_workout(workout)


def schedule_workout(client: Garmin, workout_id: int, date: str) -> dict:
    """Schedule an uploaded workout on the Garmin calendar.

    Args:
        client: Authenticated Garmin client.
        workout_id: The workoutId returned from upload_workout().
        date: Date string in YYYY-MM-DD format.
    """
    url = f"{client.garmin_workouts_schedule_url}/{workout_id}"
    return client.garth.post("connectapi", url, json={"date": date}, api=True).json()
