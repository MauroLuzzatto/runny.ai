from core.client import get_client
from core.fetch import (
    fetch_daily_stats,
    fetch_heart_rates,
    fetch_activities,
    fetch_sleep,
    fetch_user_profile,
    download_fit_files,
)
from core.models import Activity, Activities, UserProfile
from core.workouts import (
    build_simple_interval_workout,
    build_advanced_interval_workout,
    upload_workout,
    schedule_workout,
)
from core.schemas import (
    SimpleIntervalParams,
    AdvancedIntervalParams,
    build_workout_from_params,
)
from core.ai_assistant import RunningCoach
from core.suggestions import (
    SuggestionInputs,
    derive_inputs_from_garmin,
    build_suggestion_prompt,
)

__all__ = [
    "get_client",
    "fetch_daily_stats",
    "fetch_heart_rates",
    "fetch_activities",
    "fetch_sleep",
    "fetch_user_profile",
    "download_fit_files",
    "Activity",
    "Activities",
    "UserProfile",
    "build_simple_interval_workout",
    "build_advanced_interval_workout",
    "upload_workout",
    "schedule_workout",
    "SimpleIntervalParams",
    "AdvancedIntervalParams",
    "build_workout_from_params",
    "RunningCoach",
    "SuggestionInputs",
    "derive_inputs_from_garmin",
    "build_suggestion_prompt",
]
