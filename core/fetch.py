import logging
from datetime import date
from pathlib import Path

from garminconnect import Garmin

from core.models import Activity, Activities, UserProfile

logger = logging.getLogger(__name__)


def fetch_daily_stats(client: Garmin, day: str | None = None) -> dict:
    """Fetch daily summary stats (steps, calories, etc.)."""
    day = day or date.today().isoformat()
    return client.get_stats(day)


def fetch_heart_rates(client: Garmin, day: str | None = None) -> dict:
    """Fetch heart rate data for a given day."""
    day = day or date.today().isoformat()
    return client.get_heart_rates(day)


def fetch_activities(client: Garmin, start: int = 0, limit: int = 10) -> Activities:
    """Fetch recent activities and return as validated Activities model."""
    raw = client.get_activities(start=start, limit=limit)
    return Activities(items=[Activity.model_validate(a) for a in raw])


def fetch_sleep(client: Garmin, day: str | None = None) -> dict:
    """Fetch sleep data for a given day."""
    day = day or date.today().isoformat()
    return client.get_sleep_data(day)


def fetch_user_profile(client: Garmin) -> UserProfile:
    """Fetch user profile, training metrics, and race predictions from Garmin.

    Aggregates data from multiple Garmin endpoints into a single UserProfile.
    Individual endpoint failures are logged and skipped so partial data is still returned.
    """
    today = date.today().isoformat()
    data: dict = {}
    user_data: dict = {}

    # User profile (max HR, weight, lactate threshold, VO2max, etc.)
    try:
        profile = client.get_user_profile()
        user_data = profile.get("userData", {}) or {}
        data["weight_kg"] = round(user_data.get("weight", 0) / 1000, 1) or None
        data["gender"] = user_data.get("gender")
        data["vo2_max"] = user_data.get("vo2MaxRunning")
        data["lactate_threshold_hr"] = user_data.get("lactateThresholdHeartRate")
    except Exception as e:
        logger.warning("get_user_profile failed: %s", e)

    # Heart rates (resting HR, max HR from today's data)
    try:
        hr_data = client.get_heart_rates(today)
        if isinstance(hr_data, dict):
            data["resting_hr"] = hr_data.get("restingHeartRate")
    except Exception as e:
        logger.warning("get_heart_rates failed: %s", e)

    # Max HR: estimate from birth year (220 - age) if available
    try:
        birth_date = user_data.get("birthDate")
        if birth_date:
            birth_year = int(birth_date[:4])
            age = date.today().year - birth_year
            data["max_hr"] = 220 - age
    except Exception:
        pass

    # Derive HR zones from max HR using standard percentages
    max_hr = data.get("max_hr")
    if max_hr:
        data["hr_zones"] = [
            {"zone": 1, "low": int(max_hr * 0.50), "high": int(max_hr * 0.60)},
            {"zone": 2, "low": int(max_hr * 0.60), "high": int(max_hr * 0.70)},
            {"zone": 3, "low": int(max_hr * 0.70), "high": int(max_hr * 0.80)},
            {"zone": 4, "low": int(max_hr * 0.80), "high": int(max_hr * 0.90)},
            {"zone": 5, "low": int(max_hr * 0.90), "high": max_hr},
        ]

    # Training status (VO2max precise, training load, status label)
    try:
        ts = client.get_training_status(today)
        if isinstance(ts, dict):
            # VO2max (prefer precise value from training status)
            most_recent_vo2 = ts.get("mostRecentVO2Max", {})
            generic = (
                most_recent_vo2.get("generic", {})
                if isinstance(most_recent_vo2, dict)
                else {}
            )
            vo2_precise = generic.get("vo2MaxPreciseValue")
            if vo2_precise:
                data["vo2_max"] = vo2_precise

            # Training load
            load_balance = ts.get("mostRecentTrainingLoadBalance", {})
            metrics_map = load_balance.get("metricsTrainingLoadBalanceDTOMap", {})
            if metrics_map:
                # Get the first (primary) device's data
                first_device = next(iter(metrics_map.values()), {})
                total_load = sum(
                    [
                        first_device.get("monthlyLoadAerobicLow", 0),
                        first_device.get("monthlyLoadAerobicHigh", 0),
                        first_device.get("monthlyLoadAnaerobic", 0),
                    ]
                )
                if total_load:
                    data["training_load_7d"] = total_load

            # Training status label
            most_recent_status = ts.get("mostRecentTrainingStatus", {})
            latest_data = most_recent_status.get("latestTrainingStatusData", {})
            if latest_data:
                first_status = next(iter(latest_data.values()), {})
                status_label = first_status.get("trainingStatus")
                if status_label is not None:
                    data["training_status"] = str(status_label)
    except Exception as e:
        logger.warning("get_training_status failed: %s", e)

    # Training readiness
    try:
        tr = client.get_training_readiness(today)
        if isinstance(tr, dict) and tr:
            data["training_readiness"] = tr.get("score") or tr.get(
                "trainingReadinessScore"
            )
        elif isinstance(tr, list) and tr:
            data["training_readiness"] = tr[0].get("score") or tr[0].get(
                "trainingReadinessScore"
            )
    except Exception as e:
        logger.warning("get_training_readiness failed: %s", e)

    # Lactate threshold (from dedicated endpoint, more detailed)
    try:
        lt = client.get_lactate_threshold()
        if isinstance(lt, dict):
            speed_hr = lt.get("speed_and_heart_rate", {})
            if speed_hr:
                lt_hr = speed_hr.get("heartRate")
                if lt_hr:
                    data["lactate_threshold_hr"] = lt_hr
    except Exception as e:
        logger.warning("get_lactate_threshold failed: %s", e)

    # Race predictions
    try:
        race_data = client.get_race_predictions()
        if isinstance(race_data, dict):
            preds = {}
            key_map = {
                "time5K": "5k",
                "time10K": "10k",
                "timeHalfMarathon": "half_marathon",
                "timeMarathon": "marathon",
            }
            for api_key, label in key_map.items():
                val = race_data.get(api_key)
                if val:
                    preds[label] = val
            if preds:
                data["race_predictions"] = preds
    except Exception as e:
        logger.warning("get_race_predictions failed: %s", e)

    return UserProfile(**{k: v for k, v in data.items() if v is not None})


def download_fit_files(
    client: Garmin, activities: Activities, output_dir: str = "fit_files"
) -> list[Path]:
    """Download .fit files for the given activities, skipping existing ones."""
    fit_dir = Path(output_dir)
    fit_dir.mkdir(exist_ok=True)
    downloaded = []

    for a in activities.items:
        fit_path = (
            fit_dir / f"{a.start_time_local.date()}_{a.sport}_{a.activity_id}.zip"
        )
        if fit_path.exists():
            continue
        fit_data = client.download_activity(
            a.activity_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL
        )
        fit_path.write_bytes(fit_data)
        downloaded.append(fit_path)

    return downloaded
