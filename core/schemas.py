from __future__ import annotations

from pydantic import BaseModel, Field
from garminconnect.workout import RunningWorkout

from core.workouts import build_simple_interval_workout, build_steady_run


def _pace_to_ms(pace_min_km: float) -> float:
    """Convert pace in min/km to speed in m/s."""
    return 1000 / (pace_min_km * 60)


class PlannedSession(BaseModel):
    """A single session in the weekly training plan."""

    day: str = Field(description="Day of week (e.g. Mon, Tue, Wed)")
    session: str = Field(
        description="Session name (e.g. Easy Run, Threshold Intervals)"
    )
    target: str = Field(
        description="Target details (e.g. 10 km @ 5:45-6:00/km, HR <130)"
    )
    importance: str = Field(description="Key, High, Medium, or Low")


class TrainingPlan(BaseModel):
    """A weekly training plan with recommended sessions."""

    week_label: str = Field(
        description="Week label (e.g. Week 1 (Mar 23-29) — Build Structure)"
    )
    sessions: list[PlannedSession] = Field(
        description="List of planned sessions for the week"
    )
    total_km: float = Field(description="Estimated total weekly distance in km")


class SimpleIntervalParams(BaseModel):
    """Parameters for a simple time-based interval workout."""

    name: str = Field(default="5x4min Intervals", description="Workout name")
    intervals: int = Field(default=5, description="Number of interval repetitions")
    interval_seconds: int = Field(
        default=240, description="Duration of each interval in seconds"
    )
    recovery_seconds: int = Field(
        default=90, description="Duration of each recovery in seconds"
    )
    warmup_seconds: int = Field(default=600, description="Warmup duration in seconds")
    cooldown_seconds: int = Field(
        default=300, description="Cooldown duration in seconds"
    )
    warmup_pace_min_km: float = Field(
        default=6.5, description="Warmup pace in min/km (e.g. 6.5)"
    )
    interval_pace_min_km: float = Field(
        default=5.0, description="Interval pace in min/km (e.g. 5.0)"
    )
    recovery_pace_min_km: float = Field(
        default=6.5, description="Recovery jog pace in min/km (e.g. 6.5)"
    )
    cooldown_pace_min_km: float = Field(
        default=6.5, description="Cooldown pace in min/km (e.g. 6.5)"
    )
    warmup_hr_bpm_low: int = Field(
        default=110, description="Warmup target HR low (bpm)"
    )
    warmup_hr_bpm_high: int = Field(
        default=130, description="Warmup target HR high (bpm)"
    )
    interval_hr_bpm_low: int = Field(
        default=155, description="Interval target HR low (bpm)"
    )
    interval_hr_bpm_high: int = Field(
        default=175, description="Interval target HR high (bpm)"
    )
    recovery_hr_bpm_low: int = Field(
        default=100, description="Recovery target HR low (bpm)"
    )
    recovery_hr_bpm_high: int = Field(
        default=130, description="Recovery target HR high (bpm)"
    )
    cooldown_hr_bpm_low: int = Field(
        default=100, description="Cooldown target HR low (bpm)"
    )
    cooldown_hr_bpm_high: int = Field(
        default=125, description="Cooldown target HR high (bpm)"
    )


class SteadyRunParams(BaseModel):
    """Parameters for a steady-pace run (easy run, long run, tempo run).

    Use this for workouts with no intervals — just warmup, a main run block, and cooldown.
    All steps are time-based.
    """

    name: str = Field(default="Easy Run", description="Workout name")
    run_seconds: int = Field(
        default=3000, description="Main run duration in seconds (e.g. 3000 for 50min)"
    )
    warmup_seconds: int = Field(default=600, description="Warmup duration in seconds")
    cooldown_seconds: int = Field(
        default=300, description="Cooldown duration in seconds"
    )
    run_pace_min_km: float = Field(default=5.5, description="Main run pace in min/km")
    warmup_pace_min_km: float = Field(default=6.5, description="Warmup pace in min/km")
    cooldown_pace_min_km: float = Field(
        default=6.5, description="Cooldown pace in min/km"
    )
    run_hr_bpm_low: int = Field(default=130, description="Main run target HR low (bpm)")
    run_hr_bpm_high: int = Field(
        default=150, description="Main run target HR high (bpm)"
    )
    warmup_hr_bpm_low: int = Field(
        default=110, description="Warmup target HR low (bpm)"
    )
    warmup_hr_bpm_high: int = Field(
        default=130, description="Warmup target HR high (bpm)"
    )
    cooldown_hr_bpm_low: int = Field(
        default=100, description="Cooldown target HR low (bpm)"
    )
    cooldown_hr_bpm_high: int = Field(
        default=125, description="Cooldown target HR high (bpm)"
    )


def build_workout_from_params(
    params: SimpleIntervalParams | SteadyRunParams,
) -> RunningWorkout:
    """Dispatch to the correct workout builder based on the parameter type."""
    if isinstance(params, SteadyRunParams):
        return build_steady_run(
            name=params.name,
            run_seconds=params.run_seconds,
            warmup_seconds=params.warmup_seconds,
            cooldown_seconds=params.cooldown_seconds,
            run_speed_ms=_pace_to_ms(params.run_pace_min_km),
            warmup_speed_ms=_pace_to_ms(params.warmup_pace_min_km),
            cooldown_speed_ms=_pace_to_ms(params.cooldown_pace_min_km),
            run_hr=(params.run_hr_bpm_low, params.run_hr_bpm_high),
            warmup_hr=(params.warmup_hr_bpm_low, params.warmup_hr_bpm_high),
            cooldown_hr=(params.cooldown_hr_bpm_low, params.cooldown_hr_bpm_high),
        )

    if isinstance(params, SimpleIntervalParams):
        return build_simple_interval_workout(
            name=params.name,
            intervals=params.intervals,
            interval_seconds=params.interval_seconds,
            recovery_seconds=params.recovery_seconds,
            warmup_seconds=params.warmup_seconds,
            cooldown_seconds=params.cooldown_seconds,
            warmup_speed_ms=_pace_to_ms(params.warmup_pace_min_km),
            interval_speed_ms=_pace_to_ms(params.interval_pace_min_km),
            recovery_speed_ms=_pace_to_ms(params.recovery_pace_min_km),
            cooldown_speed_ms=_pace_to_ms(params.cooldown_pace_min_km),
            warmup_hr=(params.warmup_hr_bpm_low, params.warmup_hr_bpm_high),
            interval_hr=(params.interval_hr_bpm_low, params.interval_hr_bpm_high),
            recovery_hr=(params.recovery_hr_bpm_low, params.recovery_hr_bpm_high),
            cooldown_hr=(params.cooldown_hr_bpm_low, params.cooldown_hr_bpm_high),
        )
    raise TypeError(f"Unknown params type: {type(params)}")
