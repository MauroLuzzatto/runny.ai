import streamlit as st

st.set_page_config(page_title="Today's Training", page_icon="🏃", layout="centered")

# ── Schema ─────────────────────────────────────────────────────────────────────

ZONES = {
    "Z1 – Recovery":  {"short": "Z1", "color": "#D3D1C7", "text": "#444441", "hr": "60–70%", "feel": "Trivially easy"},
    "Z2 – Aerobic":   {"short": "Z2", "color": "#9FE1CB", "text": "#085041", "hr": "70–80%", "feel": "Conversational"},
    "Z3 – Tempo":     {"short": "Z3", "color": "#FAC775", "text": "#633806", "hr": "80–88%", "feel": "Comfortably hard"},
    "Z4 – Threshold": {"short": "Z4", "color": "#F5C4B3", "text": "#711e0e", "hr": "88–92%", "feel": "Hard, ~20–40 min max"},
    "Z5 – VO₂max":    {"short": "Z5", "color": "#F7C1C1", "text": "#791F1F", "hr": "92–100%", "feel": "Near max, short bursts"},
}

SESSIONS = [
    {
        "name": "Easy run",
        "zone": "Z2 – Aerobic",
        "structure": "continuous",
        "duration_min": 40,
        "load": "Low",
        "description": "Fully aerobic, conversational pace. Builds base and aids recovery.",
        "conditions": lambda i: i["days_hard"] <= 1 or i["fatigue"] >= 4 or i["weekly_km"] > i["target_km"] * 0.85,
        "reason": lambda i: (
            "Your fatigue is high — keep it easy today." if i["fatigue"] >= 4
            else "You ran hard recently. An easy day protects recovery." if i["days_hard"] <= 1
            else "You're close to your weekly target — no need to push more load."
        ),
    },
    {
        "name": "Long run",
        "zone": "Z2 – Aerobic",
        "structure": "continuous",
        "duration_min": 75,
        "load": "Medium",
        "description": "Extended aerobic effort. Builds endurance and glycogen efficiency.",
        "conditions": lambda i: i["day_of_week"] in ["Saturday", "Sunday"] and i["fatigue"] <= 2 and i["days_hard"] >= 2,
        "reason": lambda i: "Weekend + fresh legs = perfect long run window.",
    },
    {
        "name": "Tempo run",
        "zone": "Z3 – Tempo",
        "structure": "continuous",
        "duration_min": 40,
        "load": "Medium",
        "description": "Sustained comfortably hard effort. Highest return-on-investment for most runners.",
        "conditions": lambda i: i["days_hard"] >= 2 and i["fatigue"] <= 2 and i["weekly_km"] < i["target_km"] * 0.8,
        "reason": lambda i: f"You haven't hit threshold in {i['days_hard']} days and your legs are fresh — tempo is the move.",
    },
    {
        "name": "Cruise intervals",
        "zone": "Z3 – Tempo",
        "structure": "intervals",
        "duration_min": 45,
        "load": "Medium",
        "description": "3 × 10 min at tempo pace with 2 min recovery. Same zone as tempo, more structure.",
        "conditions": lambda i: i["days_hard"] >= 2 and i["fatigue"] <= 3 and i["goal"] == "Raise lactate threshold",
        "reason": lambda i: "Your goal is threshold fitness — cruise intervals let you accumulate more tempo volume.",
    },
    {
        "name": "VO₂max intervals",
        "zone": "Z5 – VO₂max",
        "structure": "intervals",
        "duration_min": 50,
        "load": "High",
        "description": "5 × 1 km at 3–5K effort with 90 s recovery. Potent but taxing.",
        "conditions": lambda i: i["days_hard"] >= 3 and i["fatigue"] <= 1 and i["goal"] == "Improve race speed",
        "reason": lambda i: "Legs are very fresh and your goal is speed — time to hit the track.",
    },
    {
        "name": "Hill repeats",
        "zone": "Z4 – Threshold",
        "structure": "hills",
        "duration_min": 45,
        "load": "High",
        "description": "8–10 × 60–90 s hill sprints. Builds strength and VO₂ with less impact than flat intervals.",
        "conditions": lambda i: i["days_hard"] >= 2 and i["fatigue"] <= 2 and i["goal"] == "Build strength & power",
        "reason": lambda i: "Hill work matches your goal and gives a high stimulus with lower injury risk than track intervals.",
    },
    {
        "name": "Easy fartlek",
        "zone": "Z2 – Aerobic",
        "structure": "fartlek",
        "duration_min": 45,
        "load": "Low–Medium",
        "description": "45 min easy with 6 × 1 min surges. Low commitment, adds variety.",
        "conditions": lambda i: i["fatigue"] == 2 and i["days_hard"] >= 2,
        "reason": lambda i: "You're somewhat fresh but not feeling a full hard session — fartlek is the honest middle ground.",
    },
    {
        "name": "Rest day",
        "zone": "Z1 – Recovery",
        "structure": "rest",
        "duration_min": 0,
        "load": "None",
        "description": "Full rest or easy walk. Adaptation happens during recovery, not during runs.",
        "conditions": lambda i: i["fatigue"] >= 5,
        "reason": lambda i: "Fatigue is very high. Rest is training — skip without guilt.",
    },
]


def recommend(inputs: dict) -> tuple[dict, list[dict]]:
    """Return (primary, [alternatives]) based on inputs."""
    scored = []
    for s in SESSIONS:
        try:
            fits = s["conditions"](inputs)
        except Exception:
            fits = False
        scored.append((s, fits))

    matching = [s for s, fits in scored if fits]
    non_matching = [s for s, fits in scored if not fits]

    if not matching:
        matching = [s for s in SESSIONS if s["name"] == "Easy run"]

    primary = matching[0]
    alts = [s for s in matching[1:] + non_matching if s["name"] != primary["name"]][:3]
    return primary, alts


def zone_badge(zone_key: str) -> str:
    z = ZONES.get(zone_key, {})
    color = z.get("color", "#eee")
    text = z.get("text", "#333")
    short = z.get("short", zone_key)
    return (
        f'<span style="background:{color};color:{text};padding:3px 10px;'
        f'border-radius:20px;font-size:12px;font-weight:600;">{short}</span>'
    )


def struct_badge(structure: str) -> str:
    return (
        f'<span style="border:1px solid #ccc;padding:3px 10px;'
        f'border-radius:20px;font-size:12px;color:#666;">{structure}</span>'
    )


# ── UI ─────────────────────────────────────────────────────────────────────────

st.title("Today's training")

with st.container():
    col1, col2 = st.columns(2)
    with col1:
        days_hard = st.slider("Days since last hard effort", 0, 7, 2)
        weekly_km = st.number_input("Km run this week", min_value=0, max_value=200, value=30, step=5)
    with col2:
        fatigue = st.select_slider(
            "How do your legs feel?",
            options=[1, 2, 3, 4, 5],
            value=2,
            format_func=lambda x: {1: "Fresh 💪", 2: "Good", 3: "OK", 4: "Tired", 5: "Cooked 😮‍💨"}[x],
        )
        target_km = st.number_input("Weekly km target", min_value=0, max_value=300, value=50, step=5)

    col3, col4 = st.columns(2)
    with col3:
        goal = st.selectbox(
            "Current training goal",
            ["Build aerobic base", "Raise lactate threshold", "Improve race speed", "Build strength & power"],
        )
    with col4:
        import datetime
        day_of_week = datetime.date.today().strftime("%A")
        st.markdown(f"**Day of week**")
        st.markdown(f"`{day_of_week}`")

st.divider()

# ── Recommendation ─────────────────────────────────────────────────────────────

inputs = {
    "days_hard": days_hard,
    "weekly_km": weekly_km,
    "target_km": target_km,
    "fatigue": fatigue,
    "goal": goal,
    "day_of_week": day_of_week,
}

primary, alts = recommend(inputs)
zone = ZONES.get(primary["zone"], {})

st.subheader("Recommended session")

with st.container(border=True):
    badges = f"{zone_badge(primary['zone'])} &nbsp; {struct_badge(primary['structure'])}"
    st.markdown(badges, unsafe_allow_html=True)
    st.markdown(f"### {primary['name']}")
    st.markdown(primary["description"])

    if primary["duration_min"] > 0:
        c1, c2, c3 = st.columns(3)
        c1.metric("Duration", f"{primary['duration_min']} min")
        c2.metric("HR target", zone.get("hr", "–"))
        c3.metric("Load", primary["load"])

    reason = primary["reason"](inputs)
    st.info(f"**Why this?** {reason}")

    st.button(f"Plan this session →", type="primary", use_container_width=True)

# ── Alternatives ───────────────────────────────────────────────────────────────

if alts:
    st.markdown("#### Or try instead")
    for alt in alts:
        az = ZONES.get(alt["zone"], {})
        with st.container(border=True):
            col_a, col_b = st.columns([3, 1])
            with col_a:
                badges_alt = f"{zone_badge(alt['zone'])} &nbsp; {struct_badge(alt['structure'])}"
                st.markdown(badges_alt, unsafe_allow_html=True)
                st.markdown(f"**{alt['name']}**")
                meta = f"{alt['duration_min']} min · {az.get('feel', '')} · Load: {alt['load']}" if alt["duration_min"] > 0 else "Full rest"
                st.caption(meta)
            with col_b:
                st.button("Select", key=f"alt_{alt['name']}", use_container_width=True)