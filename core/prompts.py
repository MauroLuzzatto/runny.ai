from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from core.models import Activities, Activity, UserProfile

_PROMPTS_DIR = Path(__file__).parent / "prompts"

ANALYSIS_SYSTEM_PROMPT = (_PROMPTS_DIR / "analysis.md").read_text()
WORKOUT_SYSTEM_PROMPT = (_PROMPTS_DIR / "workout.md").read_text()


def _format_run_summary(run: Activity) -> str:
    parts = [f"- {run.start_time_local.strftime('%Y-%m-%d')}"]
    if run.distance_km:
        parts.append(f"{run.distance_km} km")
    if run.pace_min_per_km:
        parts.append(f"pace {run.pace_min_per_km} min/km")
    if run.average_hr:
        parts.append(f"avg HR {int(run.average_hr)}")
    if run.aerobic_training_effect:
        parts.append(f"aerobic TE {run.aerobic_training_effect}")
    if run.anaerobic_training_effect:
        parts.append(f"anaerobic TE {run.anaerobic_training_effect}")
    return ", ".join(parts)


def _format_profile(profile: UserProfile) -> str:
    """Format user profile data for the system prompt."""
    lines = ["\n\nRunner profile:"]
    if profile.max_hr:
        lines.append(f"- Max heart rate: {profile.max_hr} bpm")
    if profile.resting_hr:
        lines.append(f"- Resting heart rate: {profile.resting_hr} bpm")
    if profile.vo2_max:
        lines.append(f"- VO2max: {profile.vo2_max:.1f}")
    if profile.training_status:
        lines.append(f"- Training status: {profile.training_status}")
    if profile.training_load_7d:
        lines.append(f"- 7-day training load: {profile.training_load_7d:.0f}")
    if profile.training_readiness:
        lines.append(f"- Training readiness score: {profile.training_readiness:.0f}")
    if profile.lactate_threshold_hr:
        lines.append(f"- Lactate threshold HR: {profile.lactate_threshold_hr} bpm")
    if profile.weight_kg:
        lines.append(f"- Weight: {profile.weight_kg} kg")
    if profile.hr_zones:
        zones_str = ", ".join(
            f"Z{z['zone']}: {z['low']}-{z['high']}" for z in profile.hr_zones
        )
        lines.append(f"- HR zones: {zones_str}")
    if profile.race_predictions:
        preds = []
        for key in ["5k", "10k", "half_marathon", "marathon"]:
            fmt = profile.format_race_prediction(key)
            if fmt:
                preds.append(f"{key}: {fmt}")
        if preds:
            lines.append(f"- Race predictions: {', '.join(preds)}")
    return "\n".join(lines)


def _format_activities(activities: Activities) -> str:
    """Format run data from the last 2 months for the system prompt."""
    two_months_ago = datetime.now() - timedelta(days=60)
    runs = [r for r in activities.runs() if r.start_time_local >= two_months_ago]
    if not runs:
        return ""
    lines = [f"\n\nRecent runs (last 2 months, {len(runs)} total):\n"]
    for run in runs:
        lines.append(_format_run_summary(run))
    return "\n".join(lines)


def build_analysis_prompt(
    activities: Activities | None = None,
    profile: UserProfile | None = None,
) -> str:
    """Build the system prompt for training history analysis."""
    lines = [ANALYSIS_SYSTEM_PROMPT]

    if profile:
        lines.append(_format_profile(profile))

    if activities:
        lines.append(_format_activities(activities))

    return "\n".join(lines)


def build_workout_prompt(
    training_summary: str,
    activities: Activities | None = None,
    profile: UserProfile | None = None,
) -> str:
    """Build the system prompt for workout creation.

    Args:
        training_summary: The analysis from the analysis step, injected
            so the workout coach has full context.
        activities: Optional activities for raw data reference.
        profile: Optional user profile for HR zones etc.
    """
    lines = [WORKOUT_SYSTEM_PROMPT]

    if profile:
        lines.append(_format_profile(profile))

    lines.append(f"\n\nTraining history analysis:\n{training_summary}")

    if activities:
        lines.append(_format_activities(activities))

    return "\n".join(lines)
