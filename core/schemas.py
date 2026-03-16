from __future__ import annotations

from pydantic import BaseModel, Field
from garminconnect.workout import RunningWorkout

from core.workouts import build_simple_interval_workout, build_advanced_interval_workout


class SimpleIntervalParams(BaseModel):
    """Parameters for a simple time-based interval workout."""

    name: str = Field(default="5x4min Intervals (simple)", description="Workout name")
    intervals: int = Field(default=5, description="Number of interval repetitions")
    interval_seconds: int = Field(default=240, description="Duration of each interval in seconds")
    recovery_seconds: int = Field(default=90, description="Duration of each recovery in seconds")
    warmup_seconds: int = Field(default=600, description="Warmup duration in seconds")
    cooldown_seconds: int = Field(default=300, description="Cooldown duration in seconds")


class AdvancedIntervalParams(BaseModel):
    """Parameters for a distance-based interval workout with pace & HR targets."""

    name: str = Field(default="5x1km Intervals (with targets)", description="Workout name")
    intervals: int = Field(default=5, description="Number of interval repetitions")
    interval_distance_m: int = Field(default=1000, description="Distance of each interval in meters")
    recovery_seconds: int = Field(default=90, description="Duration of each recovery in seconds")
    warmup_seconds: int = Field(default=600, description="Warmup duration in seconds")


def build_workout_from_params(params: SimpleIntervalParams | AdvancedIntervalParams) -> RunningWorkout:
    """Dispatch to the correct workout builder based on the parameter type."""
    if isinstance(params, SimpleIntervalParams):
        return build_simple_interval_workout(**params.model_dump())
    elif isinstance(params, AdvancedIntervalParams):
        return build_advanced_interval_workout(**params.model_dump())
    raise TypeError(f"Unknown params type: {type(params)}")
