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
    Individual endpoint failures are silently skipped so partial data is still returned.
    """
    today = date.today().isoformat()
    data: dict = {}

    # User profile settings (max HR, resting HR, weight, age, etc.)
    try:
        settings = client.get_userprofile_settings()
        logger.info("get_userprofile_settings keys: %s", list(settings.keys()) if isinstance(settings, dict) else type(settings))
        user_data = settings.get("userData", {})
        logger.info("userData keys: %s", list(user_data.keys()) if isinstance(user_data, dict) else type(user_data))
        data["max_hr"] = user_data.get("maxHeartRate")
        data["resting_hr"] = user_data.get("restingHeartRate")
        data["weight_kg"] = round(user_data.get("weight", 0) / 1000, 1) or None
        data["birth_year"] = user_data.get("birthYear")
        data["gender"] = user_data.get("gender")

        # HR zones from user settings
        hr_zones = settings.get("heartRateZones")
        if hr_zones:
            data["hr_zones"] = [
                {"zone": i + 1, "low": z.get("low"), "high": z.get("high")}
                for i, z in enumerate(hr_zones)
                if z.get("low") is not None
            ]
    except Exception as e:
        logger.warning("get_userprofile_settings failed: %s", e)

    # Training status (VO2max, training load, status label)
    try:
        ts = client.get_training_status(today)
        logger.info("get_training_status type=%s, value=%s", type(ts).__name__, ts)
        if ts:
            most_recent = ts[0] if isinstance(ts, list) else ts
            data["vo2_max"] = most_recent.get("vo2MaxPreciseValue") or most_recent.get("vo2MaxValue")
            data["training_load_7d"] = most_recent.get("trainingLoad7Day")
            data["training_status"] = most_recent.get("trainingStatusLabel")
    except Exception as e:
        logger.warning("get_training_status failed: %s", e)

    # Training readiness
    try:
        tr = client.get_training_readiness(today)
        logger.info("get_training_readiness type=%s, value=%s", type(tr).__name__, tr)
        if tr:
            data["training_readiness"] = tr.get("score") or tr.get("trainingReadinessScore")
    except Exception as e:
        logger.warning("get_training_readiness failed: %s", e)

    # Lactate threshold
    try:
        lt = client.get_lactate_threshold()
        logger.info("get_lactate_threshold type=%s, value=%s", type(lt).__name__, lt)
        if lt:
            data["lactate_threshold_hr"] = lt.get("lactateThresholdHeartRate")
    except Exception as e:
        logger.warning("get_lactate_threshold failed: %s", e)

    # Race predictions
    try:
        race_data = client.get_race_predictions()
        logger.info("get_race_predictions type=%s, value=%s", type(race_data).__name__, race_data)
        if race_data:
            preds = {}
            for pred in race_data if isinstance(race_data, list) else [race_data]:
                race_type = pred.get("raceType", {})
                key = race_type.get("key") if isinstance(race_type, dict) else None
                time_secs = pred.get("racePredictionInSeconds")
                if key and time_secs:
                    preds[key] = time_secs
            if preds:
                data["race_predictions"] = preds
    except Exception as e:
        logger.warning("Garmin API call failed: %s", e)

    return UserProfile(**{k: v for k, v in data.items() if v is not None})


def download_fit_files(
    client: Garmin, activities: Activities, output_dir: str = "fit_files"
) -> list[Path]:
    """Download .fit files for the given activities, skipping existing ones."""
    fit_dir = Path(output_dir)
    fit_dir.mkdir(exist_ok=True)
    downloaded = []

    for a in activities.items:
        fit_path = fit_dir / f"{a.start_time_local.date()}_{a.sport}_{a.activity_id}.zip"
        if fit_path.exists():
            continue
        fit_data = client.download_activity(
            a.activity_id, dl_fmt=client.ActivityDownloadFormat.ORIGINAL
        )
        fit_path.write_bytes(fit_data)
        downloaded.append(fit_path)

    return downloaded
