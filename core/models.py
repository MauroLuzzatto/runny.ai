from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class ActivityType(BaseModel):
    type_id: int = Field(alias="typeId")
    type_key: str = Field(alias="typeKey")
    parent_type_id: int = Field(alias="parentTypeId")

    model_config = {"populate_by_name": True}


class EventType(BaseModel):
    type_id: int = Field(alias="typeId")
    type_key: str = Field(alias="typeKey")

    model_config = {"populate_by_name": True}


class Activity(BaseModel):
    """Schema for a Garmin Connect activity.

    PII fields (GPS coordinates, location_name, device_id, manufacturer)
    are intentionally excluded. start_time_local is kept for date-based
    filtering but only the date portion is sent to the LLM.
    activity_id is kept internally for fetching splits but not sent to the LLM.
    """

    activity_id: int = Field(alias="activityId")
    activity_name: str | None = Field(None, alias="activityName")
    start_time_local: datetime = Field(alias="startTimeLocal")
    activity_type: ActivityType = Field(alias="activityType")
    event_type: EventType | None = Field(None, alias="eventType")
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
    anaerobic_training_effect: float | None = Field(
        None, alias="anaerobicTrainingEffect"
    )
    training_effect_label: str | None = Field(None, alias="trainingEffectLabel")
    activity_training_load: float | None = Field(None, alias="activityTrainingLoad")
    vo2_max: float | None = Field(None, alias="vO2MaxValue")

    # Power (running power)
    avg_power: float | None = Field(None, alias="avgPower")
    max_power: float | None = Field(None, alias="maxPower")
    norm_power: float | None = Field(None, alias="normPower")

    # Running dynamics
    avg_cadence: float | None = Field(
        None, alias="averageRunningCadenceInStepsPerMinute"
    )
    max_cadence: float | None = Field(None, alias="maxRunningCadenceInStepsPerMinute")
    avg_stride_length: float | None = Field(
        None, alias="avgStrideLength", description="cm"
    )
    avg_vertical_oscillation: float | None = Field(None, alias="avgVerticalOscillation")
    avg_ground_contact_time: float | None = Field(None, alias="avgGroundContactTime")
    avg_vertical_ratio: float | None = Field(None, alias="avgVerticalRatio")
    avg_grade_adjusted_speed: float | None = Field(None, alias="avgGradeAdjustedSpeed")
    steps: int | None = None

    # Swimming
    avg_swim_cadence: float | None = Field(
        None, alias="averageSwimCadenceInStrokesPerMinute"
    )
    avg_swolf: float | None = Field(None, alias="averageSwolf")
    active_lengths: int | None = Field(None, alias="activeLengths")
    strokes: float | None = None
    pool_length: float | None = Field(None, alias="poolLength")

    # Fastest splits
    fastest_1k: float | None = Field(
        None, alias="fastestSplit_1000", description="seconds"
    )
    fastest_mile: float | None = Field(
        None, alias="fastestSplit_1609", description="seconds"
    )
    fastest_5k: float | None = Field(
        None, alias="fastestSplit_5000", description="seconds"
    )
    fastest_100m: float | None = Field(
        None, alias="fastestSplit_100", description="seconds (swim)"
    )
    fastest_400m: float | None = Field(
        None, alias="fastestSplit_400", description="seconds (swim)"
    )

    # Intensity
    moderate_intensity_minutes: int | None = Field(
        None, alias="moderateIntensityMinutes"
    )
    vigorous_intensity_minutes: int | None = Field(
        None, alias="vigorousIntensityMinutes"
    )
    difference_body_battery: int | None = Field(None, alias="differenceBodyBattery")

    # Meta
    lap_count: int | None = Field(None, alias="lapCount")
    pr: bool = False

    # Per-lap splits (populated after fetch, not from the activities list API)
    splits: list[dict] | None = None

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


class UserProfile(BaseModel):
    """Garmin user profile and training metrics."""

    # Physical
    max_hr: int | None = None
    resting_hr: int | None = None
    weight_kg: float | None = None

    # HR zones (list of {zone, low, high})
    hr_zones: list[dict] | None = None

    # Fitness
    vo2_max: float | None = None
    training_load_7d: float | None = None
    training_status: str | None = None
    training_readiness: float | None = None
    lactate_threshold_hr: int | None = None

    # Race predictions (key -> seconds, e.g. {"5k": 1200, "10k": 2500})
    race_predictions: dict[str, float] | None = None

    def hr_zone_range(self, zone: int) -> str | None:
        """Return 'low-high' string for a given zone number."""
        if not self.hr_zones:
            return None
        for z in self.hr_zones:
            if z.get("zone") == zone:
                return f"{z['low']}-{z['high']}"
        return None

    def format_race_prediction(self, key: str) -> str | None:
        """Format a race prediction as mm:ss or h:mm:ss."""
        if not self.race_predictions or key not in self.race_predictions:
            return None
        secs = int(self.race_predictions[key])
        if secs >= 3600:
            h, rem = divmod(secs, 3600)
            m, s = divmod(rem, 60)
            return f"{h}:{m:02d}:{s:02d}"
        m, s = divmod(secs, 60)
        return f"{m}:{s:02d}"


class Activities(BaseModel):
    """Collection of activities with query helpers."""

    items: list[Activity]

    def by_sport(self, sport: str) -> list[Activity]:
        return [a for a in self.items if a.sport == sport]

    def runs(self) -> list[Activity]:
        return self.by_sport("running")

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
