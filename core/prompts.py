from __future__ import annotations

from datetime import date
from pathlib import Path

from core.models import Activities, Activity, UserProfile

_PROMPTS_DIR = Path(__file__).parent / "prompts"

SYSTEM_PROMPT = (_PROMPTS_DIR / "system.md").read_text()
ANALYSE_HISTORY_PROMPT = (_PROMPTS_DIR / "analyse_history.md").read_text()
REVIEW_EXECUTION_PROMPT = (_PROMPTS_DIR / "review_execution.md").read_text()
CREATE_WORKOUT_PROMPT = (_PROMPTS_DIR / "create_workout.md").read_text()
TRAINING_PLAN_REVIEW_PROMPT = (_PROMPTS_DIR / "training_plan_review.md").read_text()


def _format_run_summary(run: Activity) -> str:
    parts = [f"- {run.start_time_local.strftime('%Y-%m-%d')}"]
    if getattr(run, "activity_name", None):
        parts.append(f'"{run.activity_name}"')
    if getattr(run, "event_type", None):
        parts.append(f"[{run.event_type.type_key}]")
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
    if run.avg_cadence:
        parts.append(f"cadence {int(run.avg_cadence)} spm")
    if run.avg_stride_length:
        parts.append(f"stride {run.avg_stride_length:.2f} cm")
    if run.avg_ground_contact_time:
        parts.append(f"GCT {int(run.avg_ground_contact_time)} ms")
    if run.avg_vertical_oscillation:
        parts.append(f"vert osc {run.avg_vertical_oscillation:.1f} cm")
    if run.avg_vertical_ratio:
        parts.append(f"vert ratio {run.avg_vertical_ratio:.1f}%")

    summary = ", ".join(parts)

    # Append per-lap splits so the LLM can identify interval workouts
    if run.splits:
        lap_strs = []
        for i, lap in enumerate(run.splits, 1):
            s = f"  lap {i}: {lap['distance_m']}m {lap['duration_s']}s"
            if lap.get("pace_min_km"):
                s += f" @ {lap['pace_min_km']} min/km"
            if lap.get("avg_hr"):
                s += f" HR {lap['avg_hr']}"
            lap_strs.append(s)
        summary += "\n" + "\n".join(lap_strs)

    return summary


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
    """Format run data for the system prompt."""
    runs = activities.runs()
    if not runs:
        return ""
    lines = [f"\n\nRecent runs ({len(runs)} total):\n"]
    for run in runs:
        lines.append(_format_run_summary(run))
    return "\n".join(lines)


def _week_boundaries(today: date) -> tuple[date, date, date, date]:
    """Return (this_week_mon, this_week_sun, last_week_mon, last_week_sun)."""
    from datetime import timedelta

    this_mon = today - timedelta(days=today.weekday())
    this_sun = this_mon + timedelta(days=6)
    last_mon = this_mon - timedelta(days=7)
    last_sun = this_mon - timedelta(days=1)
    return this_mon, this_sun, last_mon, last_sun


def build_system_prompt(
    activities: Activities | None = None,
    profile: UserProfile | None = None,
) -> str:
    """Build the single system prompt with coach identity, runner data, and week context."""
    today = date.today()
    this_mon, this_sun, last_mon, last_sun = _week_boundaries(today)
    lines = [
        SYSTEM_PROMPT,
        f"\n\nToday's date: {today.strftime('%A, %Y-%m-%d')}",
        f"Current week (in progress, NOT complete): {this_mon.strftime('%Y-%m-%d')} (Mon) – {this_sun.strftime('%Y-%m-%d')} (Sun) — only days up to {today.strftime('%A %Y-%m-%d')} have happened",
        f"Last completed week: {last_mon.strftime('%Y-%m-%d')} (Mon) – {last_sun.strftime('%Y-%m-%d')} (Sun)",
    ]

    if profile:
        lines.append(_format_profile(profile))

    if activities:
        lines.append(_format_activities(activities))

    return "\n".join(lines)
