import pandas as pd
import streamlit as st

from datetime import date, datetime, timedelta

from core import (
    fetch_activities,
    fetch_user_profile,
    get_client,
    schedule_workout,
    upload_workout,
)
from core.ai_assistant import RunningCoach
from core.models import Activities
from core.plotting import plot_workout
from core.suggestions import derive_inputs_from_garmin

st.set_page_config(page_title="runny.ai", layout="wide")


# ── Session state defaults ──────────────────────────────────────────
if "analysis_messages" not in st.session_state:
    st.session_state.analysis_messages = []
if "workout_messages" not in st.session_state:
    st.session_state.workout_messages = []
if "coach" not in st.session_state:
    st.session_state.coach = RunningCoach()
if "garmin_client" not in st.session_state:
    st.session_state.garmin_client = None
if "activities" not in st.session_state:
    st.session_state.activities = None
if "pending_workouts" not in st.session_state:
    st.session_state.pending_workouts = []
if "garmin_defaults" not in st.session_state:
    st.session_state.garmin_defaults = {}
if "user_profile" not in st.session_state:
    st.session_state.user_profile = None
if "active_chat_tab" not in st.session_state:
    st.session_state.active_chat_tab = "analysis"


# ── Sidebar: Garmin connection ──────────────────────────────────────
with st.sidebar:
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
                st.success("Connected!")
            except Exception as e:
                st.error(f"Connection failed: {e}")

    st.divider()

    if (
        st.session_state.garmin_client is not None
        and st.session_state.activities is None
    ):
        if st.button("Load Activities (optional)", use_container_width=True):
            with st.spinner("Fetching activities..."):
                try:
                    raw = fetch_activities(st.session_state.garmin_client, limit=100)
                    st.session_state.activities = raw
                    st.session_state.coach = RunningCoach(
                        activities=raw, profile=st.session_state.user_profile
                    )
                    st.session_state.garmin_defaults = derive_inputs_from_garmin(
                        raw, profile=st.session_state.user_profile
                    )
                    st.success("Activities loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load activities: {e}")

    if (
        st.session_state.garmin_client is not None
        and st.session_state.user_profile is None
    ):
        if st.button("Load Profile (HR, VO2max, zones...)", use_container_width=True):
            with st.spinner("Fetching profile data..."):
                try:
                    profile = fetch_user_profile(st.session_state.garmin_client)
                    st.session_state.user_profile = profile
                    # Rebuild coach with profile data
                    st.session_state.coach = RunningCoach(
                        activities=st.session_state.activities,
                        profile=profile,
                    )
                    # Re-derive defaults with real max HR and readiness
                    if st.session_state.activities:
                        st.session_state.garmin_defaults = derive_inputs_from_garmin(
                            st.session_state.activities, profile=profile
                        )
                    st.success("Profile loaded!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to load profile: {e}")

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
        two_months_ago = datetime.now() - timedelta(days=60)
        runs = [r for r in activities.runs() if r.start_time_local >= two_months_ago]
        if runs:
            # Summary metrics
            st.subheader(f"Running Summary ({len(runs)} runs, last 2 months)")
            total_km = sum(r.distance_km or 0 for r in runs)
            avg_pace = sum(r.pace_min_per_km for r in runs if r.pace_min_per_km) / max(
                sum(1 for r in runs if r.pace_min_per_km), 1
            )
            avg_hr = sum(r.average_hr for r in runs if r.average_hr) / max(
                sum(1 for r in runs if r.average_hr), 1
            )
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Distance", f"{total_km:.1f} km")
            m2.metric("Avg Pace", f"{avg_pace:.2f} min/km")
            m3.metric("Avg HR", f"{avg_hr:.0f} bpm")

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


# ── Main area ───────────────────────────────────────────────────────
title_col, clear_col = st.columns([5, 1])
with title_col:
    st.title("runny.ai")
with clear_col:
    st.write("")  # vertical spacer to align with title
    if st.button("Clear Chat", use_container_width=True):
        st.session_state.analysis_messages = []
        st.session_state.workout_messages = []
        st.session_state.active_chat_tab = "analysis"
        st.session_state.coach = RunningCoach(
            activities=st.session_state.activities,
            profile=st.session_state.user_profile,
        )
        st.rerun()

# ── Training type config (used by right column) ────────────────────
TRAINING_TYPES = {
    "Easy Run": "Create an easy recovery run workout",
    "Tempo Run": "Create a tempo run workout at threshold pace",
    "Interval Training": "Create a high-intensity interval training workout",
    "Long Run": "Create a long endurance run workout",
    "Hill Repeats": "Create a hill repeat workout",
    "Fartlek": "Create a fartlek workout with varied pace changes",
    "Race Pace": "Create a race pace workout for race preparation",
}

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
    quick_tab, custom_tab = st.tabs(["Smart Coach", "Advanced Builder"])

    # ── Tab 1: Smart Coach — analyse first, then recommend ─────────
    with quick_tab:
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
            st.session_state.active_chat_tab = "analysis"
            st.session_state.quick_prompt = (
                "Provide a concise analysis of my recent training history. Include:\n"
                "1. **Volume overview**: total runs, total distance, weekly mileage trend\n"
                "2. **Intensity distribution**: breakdown of easy vs moderate vs hard sessions "
                "based on pace and heart rate\n"
                "3. **Training effect analysis**: average aerobic & anaerobic TE, how many sessions "
                "were recovery, maintaining, improving, or highly improving\n"
                "4. **Pace progression**: are my paces improving, plateauing, or declining?\n"
                "5. **Heart rate trends**: is aerobic efficiency improving (same pace at lower HR)?\n"
                "6. **Recovery patterns**: am I allowing enough recovery between hard sessions?\n"
                "7. **Strengths & weaknesses**: what am I doing well and what needs attention?\n"
                "8. **Recommendations**: specific actionable advice for the next 1-2 weeks\n\n"
                "Be specific with numbers and dates from my data."
            )

        # Step 2: Recommend
        st.markdown("**Step 2** — Get a workout recommendation")
        recommend_disabled = not has_analysis
        if recommend_disabled and has_data:
            st.caption("Run the analysis first to unlock recommendations.")
        if st.button(
            "Recommend Workout",
            use_container_width=True,
            type="primary",
            disabled=recommend_disabled,
        ):
            st.session_state.active_chat_tab = "workout"
            profile_hint = ""
            if st.session_state.user_profile:
                p = st.session_state.user_profile
                parts = []
                if p.max_hr:
                    parts.append(f"max HR {p.max_hr}")
                if p.lactate_threshold_hr:
                    parts.append(f"LT HR {p.lactate_threshold_hr}")
                if p.vo2_max:
                    parts.append(f"VO2max {p.vo2_max:.1f}")
                if p.resting_hr:
                    parts.append(f"resting HR {p.resting_hr}")
                if parts:
                    profile_hint = (
                        f" Use my profile data ({', '.join(parts)}) "
                        "to set precise pace and HR targets for each phase."
                    )
            st.session_state.quick_prompt = (
                "Based on the training analysis, recommend the best workout "
                "for today. Briefly explain your reasoning, then IMMEDIATELY "
                "call the create_simple_interval_workout or "
                "create_advanced_interval_workout tool to build it. "
                "Do not just describe the workout — you must call the tool."
                + profile_hint
            )

    # ── Tab 2: Custom — user specifies what they want ─────────────
    with custom_tab:
        gd = st.session_state.garmin_defaults
        has_garmin = bool(gd)

        # if has_garmin:
        #     st.caption("Inputs auto-filled from Garmin data. Adjust as needed.")

        training_type = st.selectbox(
            "Training type",
            options=list(TRAINING_TYPES.keys()),
            index=None,
            placeholder="Select a training type...",
        )
        available_minutes = st.number_input(
            "Available time (min)",
            min_value=0,
            max_value=180,
            value=0,
            step=5,
            help="Leave at 0 to let the coach decide",
        )

        goal = st.selectbox(
            "Training goal",
            [
                "Build aerobic base",
                "Raise lactate threshold",
                "Improve race speed",
                "Build strength & power",
            ],
            key="suggest_goal",
        )

        fatigue = st.select_slider(
            "How do your legs feel?",
            options=[1, 2, 3, 4, 5],
            value=gd.get("fatigue", 2),
            format_func=lambda x: {
                1: "1 - Fresh",
                2: "2 - Good",
                3: "3 - OK",
                4: "4 - Tired",
                5: "5 - Cooked",
            }[x],
            key="suggest_fatigue",
        )

        if st.button("Generate Workout", use_container_width=True, type="primary"):
            st.session_state.active_chat_tab = "workout"
            parts = []
            if training_type:
                parts.append(TRAINING_TYPES[training_type])
            else:
                parts.append("Create a running workout")
            if available_minutes > 0:
                parts.append(
                    f"for {available_minutes} minutes total. "
                    f"Fit everything (warmup, main set, cooldown) within {available_minutes} minutes"
                )
            parts.append(f"My training goal is: {goal}")
            fatigue_labels = {1: "fresh", 2: "good", 3: "OK", 4: "tired", 5: "cooked"}
            parts.append(f"My legs feel {fatigue_labels[fatigue]}")
            parts.append("Call the tool to create the workout immediately")
            st.session_state.quick_prompt = ". ".join(parts) + "."

    st.divider()
    st.subheader("Proposed Workouts")
    if not st.session_state.pending_workouts:
        st.caption("No workouts yet. Chat with the coach or generate one above.")

    to_remove = None
    for i, (name, workout, params) in enumerate(st.session_state.pending_workouts):
        is_latest = i == len(st.session_state.pending_workouts) - 1
        with st.expander(f"{name}", expanded=is_latest):
            # Workout summary metrics
            segments = workout.workoutSegments
            if segments:
                steps = segments[0].workoutSteps
                dur_min = workout.estimatedDurationInSecs // 60
                m1, m2 = st.columns(2)
                m1.metric("Duration", f"{dur_min} min")
                m2.metric("Steps", len(steps))

            # Intensity chart
            if params is not None:
                fig = plot_workout(params)
                st.pyplot(fig)

            # Editable name
            custom_name = st.text_input(
                "Workout name",
                value=name,
                key=f"name_{i}",
            )

            # Garmin upload / schedule
            if st.session_state.garmin_client is not None:
                schedule_date = st.date_input(
                    "Schedule for",
                    value=date.today() + timedelta(days=1),
                    min_value=date.today(),
                    key=f"date_{i}",
                )

                upload_col, schedule_col, remove_col = st.columns(3)
                with upload_col:
                    if st.button("Upload", key=f"upload_{i}", use_container_width=True):
                        workout.workoutName = custom_name
                        with st.spinner("Uploading..."):
                            try:
                                upload_workout(st.session_state.garmin_client, workout)
                                st.success(f"'{custom_name}' uploaded!")
                            except Exception as e:
                                st.error(f"Upload failed: {e}")
                with schedule_col:
                    if st.button(
                        "Upload & Schedule",
                        key=f"schedule_{i}",
                        use_container_width=True,
                    ):
                        workout.workoutName = custom_name
                        with st.spinner("Uploading & scheduling..."):
                            try:
                                result = upload_workout(
                                    st.session_state.garmin_client, workout
                                )
                                workout_id = result.get("workoutId")
                                if workout_id:
                                    schedule_workout(
                                        st.session_state.garmin_client,
                                        workout_id,
                                        str(schedule_date),
                                    )
                                    st.success(
                                        f"'{custom_name}' scheduled for {schedule_date}!"
                                    )
                                else:
                                    st.warning(
                                        "Uploaded but could not schedule — no workout ID returned."
                                    )
                            except Exception as e:
                                st.error(f"Failed: {e}")
                with remove_col:
                    if st.button("Remove", key=f"remove_{i}", use_container_width=True):
                        to_remove = i
            else:
                rm_col1, rm_col2 = st.columns([3, 1])
                with rm_col1:
                    st.caption("Connect to Garmin to upload.")
                with rm_col2:
                    if st.button("Remove", key=f"remove_{i}", use_container_width=True):
                        to_remove = i

    if to_remove is not None:
        st.session_state.pending_workouts.pop(to_remove)
        st.rerun()

# ── Left column: Chat ──────────────────────────────────────────────
with chat_col:
    all_messages = (
        st.session_state.analysis_messages + st.session_state.workout_messages
    )
    for msg in all_messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

# ── Chat input ────────────────────────────────────────────────────
user_input = st.chat_input("Ask your running coach...")
prompt = None
if "quick_prompt" in st.session_state:
    prompt = st.session_state.pop("quick_prompt")
elif user_input:
    prompt = user_input

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
    """Pick coach mode (analysis/workout) based on prompt content."""
    lower = prompt_text.lower()

    if any(kw in lower for kw in _ANALYSIS_KEYWORDS):
        return "analysis"

    if any(kw in lower for kw in _WORKOUT_KEYWORDS):
        return "workout"

    # Default to whichever tab is active
    return st.session_state.active_chat_tab


if prompt:
    coach = st.session_state.coach
    mode = _pick_mode(prompt)
    st.session_state.active_chat_tab = mode

    # Switch coach mode if needed
    if mode != coach.mode:
        if mode == "analysis":
            coach.switch_to_analysis()
        else:
            coach.switch_to_workout()

    # Pick the right message list
    if mode == "analysis":
        messages = st.session_state.analysis_messages
    else:
        messages = st.session_state.workout_messages

    messages.append({"role": "user", "content": prompt})
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

    if text is None:
        text = ""

    messages.append({"role": "assistant", "content": text})

    if captured["workout"] and captured["params"]:
        st.session_state.pending_workouts.append(
            (captured["params"].name, captured["workout"], captured["params"])
        )

    st.rerun()
