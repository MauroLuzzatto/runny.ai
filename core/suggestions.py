"""Derive training suggestion defaults from Garmin data."""

from __future__ import annotations

import datetime

from core.models import Activities, UserProfile


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

    defaults: dict = {}

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
