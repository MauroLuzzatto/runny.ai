import logging
import warnings

import pandas as pd
import streamlit as st
from datetime import date, timedelta

from core import (
    fetch_activities,
    fetch_user_profile,
    get_client,
    schedule_workout,
    upload_workout,
)
from core import ms_to_pace
from core.ai_assistant import RunningCoach
from core.models import Activities
from core.prompts import ANALYSE_HISTORY_PROMPT, REVIEW_EXECUTION_PROMPT
from core.schemas import (
    SimpleIntervalParams,
    SteadyRunParams,
    build_workout_from_params,
)


warnings.filterwarnings("ignore", message=".*use_container_width.*")

logger = logging.getLogger("runny")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")

# Suppress Streamlit's use_container_width deprecation log
for _name in logging.Logger.manager.loggerDict:
    if _name.startswith("streamlit"):
        logging.getLogger(_name).setLevel(logging.ERROR)

st.set_page_config(page_title="runny.ai", layout="wide")

# ── Privacy policy page (accessed via ?page=privacy) ─────────────
if st.query_params.get("page") == "privacy":
    from pathlib import Path

    st.title("Privacy Policy — Runny.AI")
    st.markdown(Path("docs/PRIVACY.md").read_text())
    st.stop()

# ── Session state defaults ──────────────────────────────────────────
if "analysis_messages" not in st.session_state:
    st.session_state.analysis_messages = []
if "workout_messages" not in st.session_state:
    st.session_state.workout_messages = []
if "feedback_messages" not in st.session_state:
    st.session_state.feedback_messages = []
if "coach" not in st.session_state:
    st.session_state.coach = RunningCoach()
if "garmin_client" not in st.session_state:
    st.session_state.garmin_client = None
if "activities" not in st.session_state:
    st.session_state.activities = None
if "pending_workouts" not in st.session_state:
    st.session_state.pending_workouts = []
if "user_profile" not in st.session_state:
    st.session_state.user_profile = None
if "active_chat_tab" not in st.session_state:
    st.session_state.active_chat_tab = "analysis"


# ── Sidebar: Garmin connection ──────────────────────────────────────
with st.sidebar:
    st.markdown(
        "**runny.ai** connects to your Garmin account to analyse your "
        "training, generate personalized workouts, and upload them "
        "directly to Garmin Connect. &nbsp; [Privacy Policy](?page=privacy)",
        unsafe_allow_html=True,
    )
    st.header("OpenRouter API")
    openrouter_key = st.text_input(
        "API Key",
        value=st.secrets.get("OPENROUTER_KEY", ""),
        type="password",
        key="openrouter_key",
    )
    st.text_input(
        "Model",
        value="anthropic/claude-sonnet-4-6",
        key="openrouter_model",
    )

    st.header("Garmin Connect")

    st.caption("Use your Garmin Connect account credentials to log in.")
    email = st.text_input("Email", value=st.secrets.get("GARMIN_EMAIL", ""))
    password = st.text_input(
        "Password", value=st.secrets.get("GARMIN_PASSWORD", ""), type="password"
    )

    if st.button("Connect", use_container_width=True):
        with st.spinner("Connecting to Garmin..."):
            try:
                client = get_client(email=email, password=password)
                st.session_state.garmin_client = client
                logger.info("Garmin connected successfully")
                st.success("Connected!")
            except Exception as e:
                logger.error("Garmin connection failed: %s", e)
                st.error(f"Connection failed: {e}")

    if (
        st.session_state.garmin_client is not None
        and st.session_state.activities is None
    ):
        st.caption(
            "Loads last 2 months of activities: distance, pace, heart rate, "
            "training effect, cadence, power. No GPS or personal data is sent."
        )
        if st.button("Load Activities (optional)", use_container_width=True):
            with st.spinner("Fetching activities..."):
                try:
                    raw = fetch_activities(st.session_state.garmin_client, limit=100)
                    logger.info(
                        "Loaded %d activities (%d runs)",
                        len(raw.items),
                        len(raw.runs()),
                    )
                    st.session_state.activities = raw
                    st.session_state.coach = RunningCoach(
                        activities=raw, profile=st.session_state.user_profile
                    )
                    st.success("Activities loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load activities: {e}")

    if (
        st.session_state.garmin_client is not None
        and st.session_state.user_profile is None
    ):
        st.caption(
            "Loads max/resting HR, VO2max, HR zones, training load & status, "
            "lactate threshold, race predictions. No personal identifiers."
        )
        if st.button("Load Profile (optional)", use_container_width=True):
            with st.spinner("Fetching profile data..."):
                try:
                    profile = fetch_user_profile(st.session_state.garmin_client)
                    logger.info(
                        "Profile loaded: max_hr=%s, vo2=%s, lt_hr=%s",
                        profile.max_hr,
                        profile.vo2_max,
                        profile.lactate_threshold_hr,
                    )
                    st.session_state.user_profile = profile
                    # Rebuild coach with profile data
                    st.session_state.coach = RunningCoach(
                        activities=st.session_state.activities,
                        profile=profile,
                    )
                    st.success("Profile loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load profile: {e}")

    # ── Data loaded info ──────────────────────────────────────────
    if st.session_state.activities is not None:
        activities_all: Activities = st.session_state.activities
        all_items = activities_all.items
        runs_all = activities_all.runs()
        if all_items:
            dates = sorted(a.start_time_local for a in all_items)
            earliest = dates[0].strftime("%b %d, %Y")
            latest = dates[-1].strftime("%b %d, %Y")
            days = (dates[-1] - dates[0]).days
            st.caption(
                f"Activities loaded: {len(all_items)} total "
                f"({len(runs_all)} runs) | {earliest} - {latest} ({days} days)"
            )

    if st.session_state.user_profile is not None:
        profile = st.session_state.user_profile
        has_any = any(
            [
                profile.max_hr,
                profile.resting_hr,
                profile.vo2_max,
                profile.training_status,
                profile.training_readiness,
                profile.lactate_threshold_hr,
                profile.hr_zones,
                profile.race_predictions,
            ]
        )
        with st.expander("Runner Profile", expanded=has_any):
            if not has_any:
                st.warning(
                    "Profile loaded but no data was returned. Check your Garmin account."
                )
            if profile.max_hr:
                st.write(f"**Max HR:** {profile.max_hr} bpm")
            if profile.resting_hr:
                st.write(f"**Resting HR:** {profile.resting_hr} bpm")
            if profile.vo2_max:
                st.write(f"**VO2max:** {profile.vo2_max:.1f}")
            if profile.training_status:
                st.write(f"**Training status:** {profile.training_status}")
            if profile.training_readiness is not None:
                st.write(f"**Readiness:** {profile.training_readiness:.0f}/100")
            if profile.lactate_threshold_hr:
                st.write(
                    f"**Lactate threshold HR:** {profile.lactate_threshold_hr} bpm"
                )
            if profile.hr_zones:
                st.write("**HR Zones:**")
                for z in profile.hr_zones:
                    st.caption(f"Zone {z['zone']}: {z['low']}-{z['high']} bpm")
            if profile.race_predictions:
                st.write("**Race predictions:**")
                for key in ["5k", "10k", "half_marathon", "marathon"]:
                    fmt = profile.format_race_prediction(key)
                    if fmt:
                        st.caption(f"{key}: {fmt}")

    if st.session_state.activities is not None:
        st.divider()
        activities: Activities = st.session_state.activities
        runs = activities.runs()
        if runs:
            # Summary metrics
            st.subheader(f"Running Summary ({len(runs)} runs)")
            total_km = sum(r.distance_km or 0 for r in runs)
            total_duration_min = sum(r.duration_min for r in runs)
            total_hours = int(total_duration_min // 60)
            total_mins = int(total_duration_min % 60)
            avg_pace = sum(r.pace_min_per_km for r in runs if r.pace_min_per_km) / max(
                sum(1 for r in runs if r.pace_min_per_km), 1
            )
            pace_min = int(avg_pace)
            pace_sec = int((avg_pace - pace_min) * 60)
            avg_hr = sum(r.average_hr for r in runs if r.average_hr) / max(
                sum(1 for r in runs if r.average_hr), 1
            )
            avg_cadence = sum(r.avg_cadence for r in runs if r.avg_cadence) / max(
                sum(1 for r in runs if r.avg_cadence), 1
            )
            total_elev = sum(r.elevation_gain or 0 for r in runs)
            total_calories = sum(r.calories or 0 for r in runs)

            m1, m2, m3 = st.columns(3)
            m1.metric("Total Distance", f"{total_km:.1f} km")
            m2.metric("Avg Pace", f"{pace_min}:{pace_sec:02d} /km")
            m3.metric("Avg HR", f"{avg_hr:.0f} bpm")

            m4, m5, m6 = st.columns(3)
            m4.metric("Total Time", f"{total_hours}h {total_mins}m")
            m5.metric("Avg Cadence", f"{avg_cadence:.0f} spm")
            m6.metric("Elevation Gain", f"{total_elev:.0f} m")

            # Build dataframe for charts
            df = pd.DataFrame(
                [
                    {
                        "Date": r.start_time_local.strftime("%Y-%m-%d"),
                        "Distance (km)": r.distance_km,
                        "Pace (min/km)": r.pace_min_per_km,
                        "Avg HR": int(r.average_hr) if r.average_hr else None,
                        "Aerobic TE": r.aerobic_training_effect,
                        "Anaerobic TE": r.anaerobic_training_effect,
                    }
                    for r in runs
                ]
            )
            df["Date"] = pd.to_datetime(df["Date"])
            df = df.sort_values("Date")

            # Distance bar chart
            st.caption("Distance per run")
            st.bar_chart(df.set_index("Date")["Distance (km)"])

            # Pace line chart
            st.caption("Pace trend (lower is faster)")
            st.line_chart(df.set_index("Date")["Pace (min/km)"])

            # Heart rate line chart
            st.caption("Average heart rate")
            st.line_chart(df.set_index("Date")["Avg HR"])

            # Detailed table in expander
            with st.expander("Activity details"):
                st.dataframe(
                    df.sort_values("Date", ascending=False),
                    use_container_width=True,
                    hide_index=True,
                )
        else:
            st.info("No running activities found.")

    # ── Race goal ─────────────────────────────────────────────────
    st.divider()
    st.header("Race Goal")
    st.caption("Set a target race to guide workout recommendations.")
    race_options = ["None", "5K", "10K", "Half Marathon", "Marathon"]
    default_race = st.secrets.get("RACE_TYPE", "")
    default_race_idx = (
        race_options.index(default_race) if default_race in race_options else 0
    )
    race_type = st.selectbox(
        "Race distance",
        race_options,
        index=default_race_idx,
        key="race_type",
    )
    race_date = None
    race_time_target = None
    if race_type != "None":
        default_date_str = st.secrets.get("RACE_DATE", "")
        if default_date_str:
            try:
                default_date = date.fromisoformat(default_date_str)
            except ValueError:
                default_date = date.today() + timedelta(days=60)
        else:
            default_date = date.today() + timedelta(days=60)
        race_date = st.date_input(
            "Race date",
            value=default_date,
            min_value=date.today(),
            key="race_date",
        )
        race_time_target = st.text_input(
            "Target time (optional, e.g. 25:00 or 1:45:00)",
            value=st.secrets.get("RACE_TIME_TARGET", ""),
            key="race_time_target",
        )
    # Store in session state for prompt building
    st.session_state.race_goal = {
        "race_type": race_type if race_type != "None" else None,
        "race_date": str(race_date) if race_date and race_type != "None" else None,
        "race_time_target": race_time_target or None,
    }


def _build_race_goal_hint() -> str:
    """Build a prompt hint from the race goal settings."""
    goal = st.session_state.get("race_goal", {})
    if not goal or not goal.get("race_type"):
        return ""
    parts = [f"I'm training for a {goal['race_type']}"]
    if goal.get("race_date"):
        parts.append(f"on {goal['race_date']}")
    if goal.get("race_time_target"):
        parts.append(f"with a target time of {goal['race_time_target']}")
    return " " + ". ".join(parts) + ". Tailor the workout to this goal."


# ── Main area ───────────────────────────────────────────────────────
title_col, clear_col = st.columns([5, 1])
with title_col:
    st.title("runny.ai")
with clear_col:
    st.write("")  # vertical spacer to align with title
    if st.button("Clear Chat", use_container_width=True):
        logger.info("Chat cleared")
        st.session_state.analysis_messages = []
        st.session_state.workout_messages = []
        st.session_state.feedback_messages = []
        st.session_state.active_chat_tab = "analysis"
        st.session_state.coach = RunningCoach(
            activities=st.session_state.activities,
            profile=st.session_state.user_profile,
        )
        st.rerun()

# ── Make the right column sticky so it scrolls with the page ────────
st.markdown(
    """
    <style>
    /* Gradient background */
    .stApp {
        background: linear-gradient(160deg, #0E1117 0%, #1A1F2E 40%, #1E2A3A 70%, #0E1117 100%);
    }

    /* Accent border on sidebar */
    section[data-testid="stSidebar"] {
        border-right: 2px solid #FF6B6B;
    }

    /* Colorful subheaders */
    .stApp h2 {
        background: linear-gradient(90deg, #FF6B6B, #FFA07A, #FFD700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }

    /* Sticky right column */
    div[data-testid="stColumns"] > div:nth-child(2) > div[data-testid="stVerticalBlockBorderWrapper"] {
        position: sticky;
        top: 3.5rem;
        max-height: 85vh;
        overflow-y: auto;
        align-self: flex-start;
    }

    /* Smaller headers in chat messages */
    div[data-testid="stChatMessage"] h1 { font-size: 1.2rem; margin: 0.5em 0 0.3em; }
    div[data-testid="stChatMessage"] h2 { font-size: 1.1rem; margin: 0.4em 0 0.2em; }
    div[data-testid="stChatMessage"] h3 { font-size: 1.0rem; margin: 0.3em 0 0.2em; }
    div[data-testid="stChatMessage"] h4,
    div[data-testid="stChatMessage"] h5,
    div[data-testid="stChatMessage"] h6 { font-size: 0.95rem; margin: 0.2em 0 0.1em; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Two-column layout: Chat (left) | Workouts (right) ──────────────
chat_col, workout_col = st.columns([3, 2])

# ── Right column: Controls + Proposed workouts ─────────────────────
with workout_col:
    has_data = st.session_state.activities is not None
    has_analysis = st.session_state.coach.training_summary is not None

    if not has_data:
        st.info("Connect to Garmin and load activities to get started.")

    # Step 1: Analyse
    st.markdown("**Step 1** — Analyse your training")
    analyse_disabled = not has_data
    if st.button(
        "Analyse Training History",
        use_container_width=True,
        disabled=analyse_disabled,
    ):
        logger.info("Analyse Training History clicked")
        st.session_state.active_chat_tab = "analysis"
        st.session_state.quick_prompt = ANALYSE_HISTORY_PROMPT + _build_race_goal_hint()

    if st.button(
        "Review Execution",
        use_container_width=True,
        disabled=analyse_disabled,
    ):
        logger.info("Review Execution clicked")
        st.session_state.active_chat_tab = "feedback"
        st.session_state.quick_prompt = (
            REVIEW_EXECUTION_PROMPT + _build_race_goal_hint()
        )

    # Step 2: Create sessions from the plan
    plan = st.session_state.coach.training_plan
    if plan and plan.sessions:
        st.markdown("**Step 2** — Create a workout from the plan")
        st.caption(plan.week_label)

        # Compute dates for each day from the week label (e.g. "Mar 23-29")
        import re as _re

        _day_map = {
            "mon": 0,
            "tue": 1,
            "wed": 2,
            "thu": 3,
            "fri": 4,
            "sat": 5,
            "sun": 6,
        }
        _week_start = None
        _date_match = _re.search(r"(\w+ \d+)[-–]", plan.week_label)
        if _date_match:
            try:
                from datetime import datetime as _dt

                _week_start = _dt.strptime(
                    f"{_date_match.group(1)} {date.today().year}", "%b %d %Y"
                ).date()
            except ValueError:
                pass

        for i, s in enumerate(plan.sessions):
            # Skip rest/walk days
            if any(kw in s.session.lower() for kw in ["rest", "walk", "off"]):
                continue

            # Compute the actual date for this session
            session_date = None
            day_key = s.day.lower()[:3]
            if _week_start and day_key in _day_map:
                session_date = _week_start + timedelta(days=_day_map[day_key])

            label = f"{s.day} — {s.session} ({s.importance})"
            if st.button(label, key=f"plan_session_{i}", use_container_width=True):
                logger.info("Plan session clicked: %s (date=%s)", label, session_date)
                st.session_state.active_chat_tab = "workout"
                if session_date:
                    st.session_state.plan_session_date = session_date
                st.session_state.quick_prompt = (
                    f"Create this workout: {s.session}. "
                    f"Target: {s.target}. "
                    "Set appropriate paces for all phases." + _build_race_goal_hint()
                )
                st.rerun()

    st.divider()
    st.subheader("Proposed Workouts")
    if not st.session_state.pending_workouts:
        st.caption("No workouts yet. Chat with the coach to generate one.")
    else:
        st.caption("Upload to Garmin Connect or schedule for a specific date.")

    def _params_to_df(params):
        """Convert workout params to an editable DataFrame."""
        if isinstance(params, SimpleIntervalParams):
            rows = [
                {
                    "Phase": "Warmup",
                    "Duration (s)": params.warmup_seconds,
                    "Pace (min/km)": params.warmup_pace_min_km,
                    "HR Low": params.warmup_hr_bpm_low,
                    "HR High": params.warmup_hr_bpm_high,
                    "Reps": 1,
                },
                {
                    "Phase": "Interval",
                    "Duration (s)": params.interval_seconds,
                    "Pace (min/km)": params.interval_pace_min_km,
                    "HR Low": params.interval_hr_bpm_low,
                    "HR High": params.interval_hr_bpm_high,
                    "Reps": params.intervals,
                },
                {
                    "Phase": "Recovery",
                    "Duration (s)": params.recovery_seconds,
                    "Pace (min/km)": params.recovery_pace_min_km,
                    "HR Low": params.recovery_hr_bpm_low,
                    "HR High": params.recovery_hr_bpm_high,
                    "Reps": 1,
                },
                {
                    "Phase": "Cooldown",
                    "Duration (s)": params.cooldown_seconds,
                    "Pace (min/km)": params.cooldown_pace_min_km,
                    "HR Low": params.cooldown_hr_bpm_low,
                    "HR High": params.cooldown_hr_bpm_high,
                    "Reps": 1,
                },
            ]
        elif isinstance(params, SteadyRunParams):
            rows = [
                {
                    "Phase": "Warmup",
                    "Duration (s)": params.warmup_seconds,
                    "Pace (min/km)": params.warmup_pace_min_km,
                    "HR Low": params.warmup_hr_bpm_low,
                    "HR High": params.warmup_hr_bpm_high,
                    "Reps": 1,
                },
                {
                    "Phase": "Run",
                    "Duration (s)": params.run_seconds,
                    "Pace (min/km)": params.run_pace_min_km,
                    "HR Low": params.run_hr_bpm_low,
                    "HR High": params.run_hr_bpm_high,
                    "Reps": 1,
                },
                {
                    "Phase": "Cooldown",
                    "Duration (s)": params.cooldown_seconds,
                    "Pace (min/km)": params.cooldown_pace_min_km,
                    "HR Low": params.cooldown_hr_bpm_low,
                    "HR High": params.cooldown_hr_bpm_high,
                    "Reps": 1,
                },
            ]
        else:
            return None
        return pd.DataFrame(rows)

    def _df_to_params(df, original_params):
        """Convert edited DataFrame back to workout params."""
        row_map = {r["Phase"]: r for r in df.to_dict("records")}
        if isinstance(original_params, SimpleIntervalParams):
            w, iv, rc, cd = (
                row_map["Warmup"],
                row_map["Interval"],
                row_map["Recovery"],
                row_map["Cooldown"],
            )
            return SimpleIntervalParams(
                name=original_params.name,
                intervals=int(iv["Reps"]),
                interval_seconds=int(iv["Duration (s)"]),
                recovery_seconds=int(rc["Duration (s)"]),
                warmup_seconds=int(w["Duration (s)"]),
                cooldown_seconds=int(cd["Duration (s)"]),
                warmup_pace_min_km=float(w["Pace (min/km)"]),
                interval_pace_min_km=float(iv["Pace (min/km)"]),
                recovery_pace_min_km=float(rc["Pace (min/km)"]),
                cooldown_pace_min_km=float(cd["Pace (min/km)"]),
                warmup_hr_bpm_low=int(w["HR Low"]),
                warmup_hr_bpm_high=int(w["HR High"]),
                interval_hr_bpm_low=int(iv["HR Low"]),
                interval_hr_bpm_high=int(iv["HR High"]),
                recovery_hr_bpm_low=int(rc["HR Low"]),
                recovery_hr_bpm_high=int(rc["HR High"]),
                cooldown_hr_bpm_low=int(cd["HR Low"]),
                cooldown_hr_bpm_high=int(cd["HR High"]),
            )
        elif isinstance(original_params, SteadyRunParams):
            w, r, cd = row_map["Warmup"], row_map["Run"], row_map["Cooldown"]
            return SteadyRunParams(
                name=original_params.name,
                run_seconds=int(r["Duration (s)"]),
                warmup_seconds=int(w["Duration (s)"]),
                cooldown_seconds=int(cd["Duration (s)"]),
                run_pace_min_km=float(r["Pace (min/km)"]),
                warmup_pace_min_km=float(w["Pace (min/km)"]),
                cooldown_pace_min_km=float(cd["Pace (min/km)"]),
                run_hr_bpm_low=int(r["HR Low"]),
                run_hr_bpm_high=int(r["HR High"]),
                warmup_hr_bpm_low=int(w["HR Low"]),
                warmup_hr_bpm_high=int(w["HR High"]),
                cooldown_hr_bpm_low=int(cd["HR Low"]),
                cooldown_hr_bpm_high=int(cd["HR High"]),
            )
        return None

    to_remove = None
    for i, entry in enumerate(st.session_state.pending_workouts):
        name, workout, params = entry[0], entry[1], entry[2]
        planned_date = entry[3] if len(entry) > 3 else None
        is_latest = i == len(st.session_state.pending_workouts) - 1
        with st.expander(f"{name}", expanded=is_latest):
            overview_tab, edit_tab = st.tabs(["Overview", "Edit"])

            with overview_tab:
                # Workout summary
                dur_min = workout.estimatedDurationInSecs // 60
                st.caption(f"{dur_min} min | {workout.description or ''}")

                # Phase table
                def _format_step(step_data, reps=None):
                    """Format a single step into a table row dict."""
                    key = step_data["stepType"]["stepTypeKey"]
                    phase = key.replace("_", " ").capitalize()
                    if reps:
                        phase = f"{phase} (x{reps})"

                    v1 = step_data.get("targetValueOne")
                    v2 = step_data.get("targetValueTwo")
                    avg_speed = (v1 + v2) / 2 if v1 and v2 else None
                    pace = f"{ms_to_pace(v1)}-{ms_to_pace(v2)}/km" if v1 and v2 else "—"

                    end_val = step_data.get("endConditionValue", 0) or 0
                    end_key = step_data["endCondition"]["conditionTypeKey"]

                    if end_key == "time":
                        time_s = int(end_val)
                        time_str = f"{time_s // 60}:{time_s % 60:02d}"
                        dist_str = (
                            f"{end_val * avg_speed / 1000:.1f} km" if avg_speed else "—"
                        )
                    elif end_key == "distance":
                        dist_m = int(end_val)
                        dist_str = (
                            f"{dist_m / 1000:.1f} km"
                            if dist_m >= 1000
                            else f"{dist_m}m"
                        )
                        if avg_speed and avg_speed > 0:
                            est_secs = int(end_val / avg_speed)
                            time_str = f"{est_secs // 60}:{est_secs % 60:02d}"
                        else:
                            time_str = "—"
                    else:
                        time_str = "open"
                        dist_str = "—"

                    sec_v1 = step_data.get("secondaryTargetValueOne")
                    sec_v2 = step_data.get("secondaryTargetValueTwo")
                    hr_str = (
                        f"{int(sec_v1)}-{int(sec_v2)}" if sec_v1 and sec_v2 else "—"
                    )

                    return {
                        "Phase": phase,
                        "Time": time_str,
                        "Distance": dist_str,
                        "Pace": pace,
                        "HR (bpm)": hr_str,
                    }

                phases = []
                segments = workout.workoutSegments
                if segments:
                    for step in segments[0].workoutSteps:
                        d = step.model_dump()
                        if d.get("type") == "RepeatGroupDTO":
                            reps = d.get("numberOfIterations", 1)
                            for sub in d.get("workoutSteps", []):
                                phases.append(_format_step(sub, reps=reps))
                        else:
                            phases.append(_format_step(d))

                if phases:
                    st.dataframe(
                        pd.DataFrame(phases),
                        use_container_width=True,
                        hide_index=True,
                        height=min(len(phases) * 36 + 38, 200),
                    )

            with edit_tab:
                edit_df = _params_to_df(params)
                if edit_df is not None:
                    edited = st.data_editor(
                        edit_df,
                        use_container_width=True,
                        hide_index=True,
                        key=f"edit_{i}",
                        disabled=["Phase"],
                        column_config={
                            "Phase": st.column_config.TextColumn("Phase"),
                            "Duration (s)": st.column_config.NumberColumn(
                                "Duration (s)", min_value=0, step=10
                            ),
                            "Pace (min/km)": st.column_config.NumberColumn(
                                "Pace (min/km)",
                                min_value=2.0,
                                max_value=12.0,
                                step=0.1,
                                format="%.1f",
                            ),
                            "HR Low": st.column_config.NumberColumn(
                                "HR Low", min_value=60, max_value=220, step=1
                            ),
                            "HR High": st.column_config.NumberColumn(
                                "HR High", min_value=60, max_value=220, step=1
                            ),
                            "Reps": st.column_config.NumberColumn(
                                "Reps", min_value=1, max_value=30, step=1
                            ),
                        },
                    )
                    if st.button(
                        "Apply Changes", key=f"apply_{i}", use_container_width=True
                    ):
                        new_params = _df_to_params(edited, params)
                        if new_params:
                            new_workout = build_workout_from_params(new_params)
                            st.session_state.pending_workouts[i] = (
                                name,
                                new_workout,
                                new_params,
                                planned_date,
                            )
                            logger.info("Workout modified: %s", name)
                            st.rerun()
                else:
                    st.caption("Editing not available for this workout type.")

            # Editable name
            custom_name = st.text_input(
                "Workout name",
                value=name,
                key=f"name_{i}",
            )

            # Garmin upload / schedule
            if st.session_state.garmin_client is not None:
                default_date = planned_date
                if not default_date or default_date < date.today():
                    default_date = date.today() + timedelta(days=1)
                schedule_date = st.date_input(
                    "Schedule for",
                    value=default_date,
                    min_value=date.today(),
                    key=f"date_{i}",
                )

                c1, c2, c3 = st.columns(3)
                with c1:
                    if st.button("Upload", key=f"upload_{i}", use_container_width=True):
                        workout.workoutName = custom_name
                        with st.spinner("Uploading..."):
                            try:
                                upload_workout(st.session_state.garmin_client, workout)
                                logger.info("Workout uploaded: %s", custom_name)
                                st.success("Uploaded!")
                            except Exception as e:
                                logger.error(
                                    "Upload failed for '%s': %s", custom_name, e
                                )
                                st.error(f"Upload failed: {e}")
                with c2:
                    if st.button(
                        "Upload & Schedule",
                        key=f"schedule_{i}",
                        use_container_width=True,
                    ):
                        workout.workoutName = custom_name
                        with st.spinner("Scheduling..."):
                            try:
                                result = upload_workout(
                                    st.session_state.garmin_client, workout
                                )
                                wid = result.get("workoutId")
                                if wid:
                                    schedule_workout(
                                        st.session_state.garmin_client,
                                        wid,
                                        str(schedule_date),
                                    )
                                    logger.info(
                                        "Scheduled: %s for %s (ID=%s)",
                                        custom_name,
                                        schedule_date,
                                        wid,
                                    )
                                    st.success(f"Scheduled for {schedule_date}!")
                                else:
                                    st.warning("No workout ID returned.")
                            except Exception as e:
                                logger.error(
                                    "Schedule failed for '%s': %s", custom_name, e
                                )
                                st.error(f"Failed: {e}")
                with c3:
                    if st.button("Remove", key=f"remove_{i}", use_container_width=True):
                        to_remove = i
            else:
                if st.button("Remove", key=f"remove_{i}", use_container_width=True):
                    to_remove = i

    if to_remove is not None:
        logger.info("Workout removed at index %d", to_remove)
        st.session_state.pending_workouts.pop(to_remove)
        st.rerun()

# ── Left column: Chat ──────────────────────────────────────────────
with chat_col:
    all_messages = (
        st.session_state.analysis_messages
        + st.session_state.workout_messages
        + st.session_state.feedback_messages
    )
    for msg in all_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────
user_input = st.chat_input("Ask your running coach...")
prompt = None
if "quick_prompt" in st.session_state:
    prompt = st.session_state.pop("quick_prompt")
    logger.info("Prompt from quick_prompt: %s...", prompt[:80])
elif user_input:
    prompt = user_input
    logger.info("Prompt from chat input: %s...", prompt[:80])
else:
    logger.debug("No prompt this run")

_FEEDBACK_KEYWORDS = {
    "execution",
    "executed",
    "pacing",
    "splits",
    "grade",
    "feedback",
    "review how",
    "hr drift",
}
_ANALYSIS_KEYWORDS = {
    "analyse",
    "analysis",
    "history",
    "training effect",
    "training load",
    "review my",
}
_WORKOUT_KEYWORDS = {
    "create",
    "generate",
    "build",
    "workout",
    "recommend",
    "suggest",
    "recommendation",
    "training goal",
}


def _pick_mode(prompt_text: str) -> str:
    """Pick coach mode (analysis/workout/feedback) based on prompt content.

    Workout keywords are checked first since they're most specific.
    """
    lower = prompt_text.lower()

    if any(kw in lower for kw in _WORKOUT_KEYWORDS):
        return "workout"

    if any(kw in lower for kw in _FEEDBACK_KEYWORDS):
        return "feedback"

    if any(kw in lower for kw in _ANALYSIS_KEYWORDS):
        return "analysis"

    # Default to whichever tab is active
    return st.session_state.active_chat_tab


if prompt:
    coach = st.session_state.coach
    mode = _pick_mode(prompt)
    logger.info("Mode: %s (coach was: %s)", mode, coach.mode)
    st.session_state.active_chat_tab = mode

    # Switch coach mode if needed
    if mode == "analysis" and coach.mode != "analysis":
        logger.info("Switching coach to analysis mode")
        coach.switch_to_analysis()
    elif mode == "workout" and coach.mode != "workout":
        logger.info("Switching coach to workout mode")
        coach.switch_to_workout()
    elif mode == "feedback" and coach.mode != "feedback":
        logger.info("Switching coach to feedback mode")
        coach.switch_to_feedback()
    logger.info("Coach mode now: %s", coach.mode)

    # Pick the right message list
    if mode == "analysis":
        messages = st.session_state.analysis_messages
    elif mode == "feedback":
        messages = st.session_state.feedback_messages
    else:
        messages = st.session_state.workout_messages

    messages.append({"role": "user", "content": prompt})

    # Show a spinner in the workout column while generating
    if mode == "workout":
        with workout_col:
            status_placeholder = st.empty()
            status_placeholder.info("Creating workout...")

    with chat_col:
        with st.chat_message("user"):
            st.markdown(prompt)

        with st.chat_message("assistant"):
            captured = {"workout": None, "params": None}
            try:
                stream = st.session_state.coach.chat_stream(prompt)

                def _stream_with_capture():
                    for chunk in stream:
                        if isinstance(chunk, str):
                            yield chunk
                        elif isinstance(chunk, tuple):
                            captured["workout"], captured["params"] = chunk

                text = st.write_stream(_stream_with_capture())
            except Exception as e:
                text = f"Sorry, I encountered an error: {e}"
                st.markdown(text)

    if mode == "workout":
        status_placeholder.empty()

    if text is None:
        text = ""

    messages.append({"role": "assistant", "content": text})

    if captured["workout"] and captured["params"]:
        planned_date = st.session_state.pop("plan_session_date", None)
        logger.info(
            "Workout created: %s (scheduled=%s)", captured["params"].name, planned_date
        )
        st.session_state.pending_workouts.append(
            (
                captured["params"].name,
                captured["workout"],
                captured["params"],
                planned_date,
            )
        )

    st.rerun()
