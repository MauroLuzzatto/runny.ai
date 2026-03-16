from datetime import date
from pathlib import Path

from garminconnect import Garmin

from core.models import Activity, Activities


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
