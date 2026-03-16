from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ActivityType(BaseModel):
    type_id: int = Field(alias="typeId")
    type_key: str = Field(alias="typeKey")
    parent_type_id: int = Field(alias="parentTypeId")

    model_config = {"populate_by_name": True}


class Activity(BaseModel):
    """Schema for a Garmin Connect activity."""

    activity_id: int = Field(alias="activityId")
    activity_name: str = Field(alias="activityName")
    start_time_local: datetime = Field(alias="startTimeLocal")
    start_time_gmt: datetime = Field(alias="startTimeGMT")
    activity_type: ActivityType = Field(alias="activityType")
    sport_type_id: int = Field(alias="sportTypeId")

    # Distance & duration
    distance: float | None = Field(None, description="Distance in meters")
    duration: float = Field(description="Duration in seconds")
    elapsed_duration: float | None = Field(None, alias="elapsedDuration")
    moving_duration: float | None = Field(None, alias="movingDuration")

    # Speed
    average_speed: float | None = Field(None, alias="averageSpeed", description="m/s")
    max_speed: float | None = Field(None, alias="maxSpeed", description="m/s")

    # Elevation
    elevation_gain: float | None = Field(None, alias="elevationGain")
    elevation_loss: float | None = Field(None, alias="elevationLoss")
    min_elevation: float | None = Field(None, alias="minElevation")
    max_elevation: float | None = Field(None, alias="maxElevation")

    # Heart rate
    average_hr: float | None = Field(None, alias="averageHR")
    max_hr: float | None = Field(None, alias="maxHR")
    hr_zone_1: float | None = Field(None, alias="hrTimeInZone_1")
    hr_zone_2: float | None = Field(None, alias="hrTimeInZone_2")
    hr_zone_3: float | None = Field(None, alias="hrTimeInZone_3")
    hr_zone_4: float | None = Field(None, alias="hrTimeInZone_4")
    hr_zone_5: float | None = Field(None, alias="hrTimeInZone_5")

    # Calories
    calories: float | None = None
    bmr_calories: float | None = Field(None, alias="bmrCalories")

    # Training effect
    aerobic_training_effect: float | None = Field(None, alias="aerobicTrainingEffect")
    anaerobic_training_effect: float | None = Field(None, alias="anaerobicTrainingEffect")
    training_effect_label: str | None = Field(None, alias="trainingEffectLabel")
    activity_training_load: float | None = Field(None, alias="activityTrainingLoad")
    vo2_max: float | None = Field(None, alias="vO2MaxValue")

    # Power (running power)
    avg_power: float | None = Field(None, alias="avgPower")
    max_power: float | None = Field(None, alias="maxPower")
    norm_power: float | None = Field(None, alias="normPower")

    # Running dynamics
    avg_cadence: float | None = Field(None, alias="averageRunningCadenceInStepsPerMinute")
    max_cadence: float | None = Field(None, alias="maxRunningCadenceInStepsPerMinute")
    avg_stride_length: float | None = Field(None, alias="avgStrideLength", description="cm")
    avg_vertical_oscillation: float | None = Field(None, alias="avgVerticalOscillation")
    avg_ground_contact_time: float | None = Field(None, alias="avgGroundContactTime")
    avg_vertical_ratio: float | None = Field(None, alias="avgVerticalRatio")
    avg_grade_adjusted_speed: float | None = Field(None, alias="avgGradeAdjustedSpeed")
    steps: int | None = None

    # Swimming
    avg_swim_cadence: float | None = Field(None, alias="averageSwimCadenceInStrokesPerMinute")
    avg_swolf: float | None = Field(None, alias="averageSwolf")
    active_lengths: int | None = Field(None, alias="activeLengths")
    strokes: float | None = None
    pool_length: float | None = Field(None, alias="poolLength")

    # Location
    start_latitude: float | None = Field(None, alias="startLatitude")
    start_longitude: float | None = Field(None, alias="startLongitude")
    end_latitude: float | None = Field(None, alias="endLatitude")
    end_longitude: float | None = Field(None, alias="endLongitude")
    location_name: str | None = Field(None, alias="locationName")

    # Fastest splits
    fastest_1k: float | None = Field(None, alias="fastestSplit_1000", description="seconds")
    fastest_mile: float | None = Field(None, alias="fastestSplit_1609", description="seconds")
    fastest_5k: float | None = Field(None, alias="fastestSplit_5000", description="seconds")
    fastest_100m: float | None = Field(None, alias="fastestSplit_100", description="seconds (swim)")
    fastest_400m: float | None = Field(None, alias="fastestSplit_400", description="seconds (swim)")

    # Intensity
    moderate_intensity_minutes: int | None = Field(None, alias="moderateIntensityMinutes")
    vigorous_intensity_minutes: int | None = Field(None, alias="vigorousIntensityMinutes")
    difference_body_battery: int | None = Field(None, alias="differenceBodyBattery")

    # Meta
    lap_count: int | None = Field(None, alias="lapCount")
    manufacturer: str | None = None
    device_id: int | None = Field(None, alias="deviceId")
    favorite: bool = False
    pr: bool = False

    model_config = {"populate_by_name": True}

    # --- convenience properties ---

    @property
    def sport(self) -> str:
        return self.activity_type.type_key

    @property
    def distance_km(self) -> float | None:
        return round(self.distance / 1000, 2) if self.distance else None

    @property
    def duration_min(self) -> float:
        return round(self.duration / 60, 1)

    @property
    def pace_min_per_km(self) -> float | None:
        """Average pace in min/km."""
        if not self.distance or self.distance == 0:
            return None
        return round((self.duration / 60) / (self.distance / 1000), 2)


class Activities(BaseModel):
    """Collection of activities with query helpers."""

    items: list[Activity]

    def by_sport(self, sport: str) -> list[Activity]:
        return [a for a in self.items if a.sport == sport]

    def runs(self) -> list[Activity]:
        return self.by_sport("running")

    def swims(self) -> list[Activity]:
        return self.by_sport("lap_swimming")

    def after(self, dt: datetime) -> list[Activity]:
        return [a for a in self.items if a.start_time_local > dt]

    def before(self, dt: datetime) -> list[Activity]:
        return [a for a in self.items if a.start_time_local < dt]

    def with_hr_above(self, bpm: float) -> list[Activity]:
        return [a for a in self.items if a.max_hr and a.max_hr > bpm]

    def longest(self, n: int = 1) -> list[Activity]:
        return sorted(self.items, key=lambda a: a.distance or 0, reverse=True)[:n]

    def fastest_pace(self, n: int = 1) -> list[Activity]:
        paced = [a for a in self.items if a.pace_min_per_km is not None]
        return sorted(paced, key=lambda a: a.pace_min_per_km)[:n]
