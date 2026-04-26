"""Test creating and uploading a workout to Garmin Connect.

Run with: uv run pytest tests/test_workout_upload.py -v
Requires valid Garmin credentials in .streamlit/secrets.toml.
"""

import pytest
import streamlit as st
from garminconnect import Garmin

from core.schemas import (
    SimpleIntervalParams,
    SteadyRunParams,
    build_workout_from_params,
)
from core.workouts import upload_workout, ms_to_pace


@pytest.fixture(scope="module")
def garmin_client():
    """Authenticate and return a Garmin client."""
    email = st.secrets.get("GARMIN_EMAIL")
    password = st.secrets.get("GARMIN_PASSWORD")
    if not email or not password:
        pytest.skip("Garmin credentials not configured in .streamlit/secrets.toml")
    client = Garmin(email, password)
    client.login()
    return client


# ── Unit tests (no Garmin connection needed) ─────────────────────


class TestSimpleWorkoutCreation:
    def test_default_params(self):
        params = SimpleIntervalParams()
        workout = build_workout_from_params(params)
        assert workout.workoutName == "5x4min Intervals"
        assert workout.estimatedDurationInSecs > 0
        assert len(workout.workoutSegments) == 1

    def test_custom_paces(self):
        params = SimpleIntervalParams(
            name="Tempo Session",
            intervals=4,
            interval_seconds=300,
            recovery_seconds=60,
            warmup_seconds=600,
            cooldown_seconds=300,
            warmup_pace_min_km=6.5,
            interval_pace_min_km=4.8,
            recovery_pace_min_km=6.5,
            cooldown_pace_min_km=6.5,
        )
        workout = build_workout_from_params(params)
        assert workout.workoutName == "Tempo Session"

        steps = workout.workoutSegments[0].workoutSteps
        # warmup, repeat group, cooldown
        assert len(steps) == 3

        # Check warmup has pace target
        warmup = steps[0]
        assert warmup.targetValueOne is not None
        assert warmup.targetValueTwo is not None
        assert warmup.description is not None
        assert "/km" in warmup.description

        # Check interval inside repeat group has pace target
        repeat = steps[1]
        interval = repeat.workoutSteps[0]
        assert interval.targetValueOne is not None
        assert "pace.zone" in str(interval.targetType)

        # Check cooldown has pace target
        cooldown = steps[2]
        assert cooldown.targetValueOne is not None

    def test_total_duration(self):
        params = SimpleIntervalParams(
            intervals=3,
            interval_seconds=200,
            recovery_seconds=60,
            warmup_seconds=300,
            cooldown_seconds=300,
        )
        workout = build_workout_from_params(params)
        expected = 300 + 3 * (200 + 60) + 300
        assert workout.estimatedDurationInSecs == expected

    def test_description_includes_paces(self):
        params = SimpleIntervalParams(
            name="Test",
            intervals=3,
            interval_seconds=240,
            interval_pace_min_km=5.0,
            warmup_pace_min_km=6.5,
        )
        workout = build_workout_from_params(params)
        assert "5:00/km" in workout.description
        assert "6:2" in workout.description  # 6:29/km approx


class TestSteadyRunCreation:
    def test_default_params(self):
        params = SteadyRunParams()
        workout = build_workout_from_params(params)
        assert workout.workoutName == "Easy Run"
        assert len(workout.workoutSegments) == 1

    def test_all_steps_time_based(self):
        params = SteadyRunParams(
            name="Easy Run",
            run_seconds=3000,
            warmup_seconds=600,
            cooldown_seconds=300,
            run_pace_min_km=5.5,
        )
        workout = build_workout_from_params(params)
        steps = workout.workoutSegments[0].workoutSteps

        for step in steps:
            d = step.model_dump()
            assert d["endCondition"]["conditionTypeKey"] == "time"

    def test_total_duration(self):
        params = SteadyRunParams(
            run_seconds=3000,
            warmup_seconds=600,
            cooldown_seconds=300,
        )
        workout = build_workout_from_params(params)
        assert workout.estimatedDurationInSecs == 3900


class TestPaceConversion:
    def test_5_min_km(self):
        assert ms_to_pace(3.33) == "5:00"

    def test_4_min_km(self):
        assert ms_to_pace(4.17) == "3:59"

    def test_6_min_km(self):
        assert ms_to_pace(2.78) == "5:59"


# ── Integration test (requires Garmin connection) ────────────────


class TestWorkoutUpload:
    def test_create_and_upload(self, garmin_client):
        """Create a workout with pace targets and upload it to Garmin Connect."""
        params = SimpleIntervalParams(
            name="[TEST] Tempo Run",
            intervals=3,
            interval_seconds=180,
            recovery_seconds=60,
            warmup_seconds=300,
            cooldown_seconds=300,
            warmup_pace_min_km=6.5,
            interval_pace_min_km=5.0,
            recovery_pace_min_km=6.5,
            cooldown_pace_min_km=6.5,
        )
        workout = build_workout_from_params(params)
        result = upload_workout(garmin_client, workout)

        assert "workoutId" in result
        assert result["workoutName"] == "[TEST] Tempo Run"
        print(f"Uploaded workout: ID={result['workoutId']}")
