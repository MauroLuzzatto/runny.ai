"""User input collection and prompt building for AI-driven training suggestions.

Collects the runner's current state (manually or from Garmin data) and
builds a rich prompt so the AI coach can make a personalized recommendation.
"""

from __future__ import annotations

import datetime
from typing import Literal

from pydantic import BaseModel, Field

from core.models import Activities, UserProfile

GOALS = Literal[
    "Build aerobic base",
    "Raise lactate threshold",
    "Improve race speed",
    "Build strength & power",
]


class SuggestionInputs(BaseModel):
    """Runner's current state for the AI coach to base recommendations on."""

    days_hard: int = Field(ge=0, le=7, description="Days since last hard effort")
    weekly_km: float = Field(ge=0, description="Km run this week")
    target_km: float = Field(ge=0, description="Weekly km target")
    fatigue: int = Field(ge=1, le=5, description="1 = fresh, 5 = cooked")
    goal: GOALS
    day_of_week: str = Field(default_factory=lambda: datetime.date.today().strftime("%A"))


def derive_inputs_from_garmin(
    activities: Activities,
    profile: UserProfile | None = None,
) -> dict:
    """Derive suggestion input defaults from Garmin activity and profile data.

    Returns a dict of field_name -> derived_value suitable as defaults
    for the UI controls. Uses real max HR from profile when available.
    """
    today = datetime.date.today()
    runs = activities.runs()

    defaults: dict = {
        "day_of_week": today.strftime("%A"),
    }

    if not runs:
        return defaults

    # weekly_km: sum of run distances since last Monday
    monday = today - datetime.timedelta(days=today.weekday())
    weekly_km = sum(
        r.distance_km or 0
        for r in runs
        if r.start_time_local.date() >= monday
    )
    defaults["weekly_km"] = round(weekly_km, 1)

    # Max HR: prefer profile, fall back to activity data, then 190
    if profile and profile.max_hr:
        max_hr = float(profile.max_hr)
    else:
        max_hrs = [r.max_hr for r in runs if r.max_hr]
        max_hr = max(max_hrs) if max_hrs else 190.0

    # Z4 threshold at 88% of max HR
    z4_threshold = max_hr * 0.88

    # days_hard: days since last run with avg HR above Z4 threshold
    for r in sorted(runs, key=lambda a: a.start_time_local, reverse=True):
        if r.average_hr and r.average_hr > z4_threshold:
            delta = (today - r.start_time_local.date()).days
            defaults["days_hard"] = min(delta, 7)
            break
    else:
        defaults["days_hard"] = 7

    # fatigue: prefer training readiness from profile, fall back to load heuristic
    if profile and profile.training_readiness is not None:
        # Garmin readiness is 0-100 (higher = more ready). Invert to fatigue 1-5.
        readiness = profile.training_readiness
        if readiness >= 80:
            defaults["fatigue"] = 1
        elif readiness >= 60:
            defaults["fatigue"] = 2
        elif readiness >= 40:
            defaults["fatigue"] = 3
        elif readiness >= 20:
            defaults["fatigue"] = 4
        else:
            defaults["fatigue"] = 5
    else:
        three_days_ago = today - datetime.timedelta(days=3)
        recent_loads = [
            r.activity_training_load or 0
            for r in runs
            if r.start_time_local.date() >= three_days_ago
        ]
        total_load = sum(recent_loads)
        if total_load == 0:
            defaults["fatigue"] = 1
        elif total_load < 100:
            defaults["fatigue"] = 2
        elif total_load < 200:
            defaults["fatigue"] = 3
        elif total_load < 300:
            defaults["fatigue"] = 4
        else:
            defaults["fatigue"] = 5

    return defaults


def build_suggestion_prompt(
    inputs: SuggestionInputs,
    activities: Activities | None = None,
    profile: UserProfile | None = None,
) -> str:
    """Build a prompt for the AI coach that includes the user's current state,
    profile data, and training history, asking it to recommend and create a workout."""
    parts = [
        "Based on my current state and training data, recommend the best workout for today, "
        "explain your reasoning, then create the workout.",
        "",
        "My current state:",
        f"- Day: {inputs.day_of_week}",
        f"- Fatigue level: {inputs.fatigue}/5 (1 = fresh, 5 = cooked)",
        f"- Days since last hard effort: {inputs.days_hard}",
        f"- Weekly volume so far: {inputs.weekly_km} km (target: {inputs.target_km} km)",
        f"- Training goal: {inputs.goal}",
    ]

    # Include profile data for personalized targets
    if profile:
        parts.append("")
        parts.append("My physiological profile:")
        if profile.max_hr:
            parts.append(f"- Max heart rate: {profile.max_hr} bpm")
        if profile.resting_hr:
            parts.append(f"- Resting heart rate: {profile.resting_hr} bpm")
        if profile.vo2_max:
            parts.append(f"- VO2max: {profile.vo2_max:.1f}")
        if profile.lactate_threshold_hr:
            parts.append(f"- Lactate threshold HR: {profile.lactate_threshold_hr} bpm")
        if profile.training_status:
            parts.append(f"- Training status: {profile.training_status}")
        if profile.training_readiness is not None:
            parts.append(f"- Training readiness: {profile.training_readiness:.0f}/100")
        if profile.hr_zones:
            zones_str = ", ".join(
                f"Z{z['zone']}: {z['low']}-{z['high']} bpm"
                for z in profile.hr_zones
            )
            parts.append(f"- HR zones: {zones_str}")
        if profile.race_predictions:
            preds = []
            for key in ["5k", "10k", "half_marathon", "marathon"]:
                fmt = profile.format_race_prediction(key)
                if fmt:
                    preds.append(f"{key}: {fmt}")
            if preds:
                parts.append(f"- Race predictions: {', '.join(preds)}")

    if activities:
        runs = activities.runs()
        if runs:
            paces = [r.pace_min_per_km for r in runs[:10] if r.pace_min_per_km]
            hrs = [r.average_hr for r in runs[:10] if r.average_hr]
            if paces:
                avg_pace = sum(paces) / len(paces)
                best_pace = min(paces)
                parts.append(f"- Recent average pace: {avg_pace:.2f} min/km (best: {best_pace:.2f} min/km)")
            if hrs:
                avg_hr = sum(hrs) / len(hrs)
                parts.append(f"- Recent average HR: {avg_hr:.0f} bpm")

    parts.append("")
    parts.append(
        "Use my HR zones and physiological data to set precise targets. "
        "Consider my fatigue, recovery status, weekly volume, and goal to pick "
        "the right session type and intensity."
    )
    return "\n".join(parts)
