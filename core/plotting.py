from __future__ import annotations

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
from matplotlib.figure import Figure

from core.schemas import AdvancedIntervalParams, SimpleIntervalParams

# Color palette
_COLORS = {
    "warmup": "#4CAF50",
    "interval": "#F44336",
    "recovery": "#2196F3",
    "cooldown": "#9C27B0",
}

_INTENSITY = {
    "warmup": 2,
    "interval": 4,
    "recovery": 1,
    "cooldown": 2,
}

_INTENSITY_LABELS = {1: "Easy", 2: "Moderate", 3: "Hard", 4: "VO₂max"}

# Target pace (min/km) and HR (bpm) per phase type
_PACE = {
    "warmup": 6.5,
    "interval": 4.5,
    "recovery": 7.0,
    "cooldown": 6.5,
}

_HR = {
    "warmup": 135,
    "interval": 175,
    "recovery": 120,
    "cooldown": 130,
}

_HR_ZONE = {
    "warmup": "Z2",
    "interval": "Z4-5",
    "recovery": "Z1",
    "cooldown": "Z2",
}


def _build_phases(params: SimpleIntervalParams | AdvancedIntervalParams) -> list[dict]:
    """Build a list of phase dicts with label, duration_s, type, intensity, pace, and hr."""
    phases: list[dict] = []

    phases.append({
        "label": "WU",
        "duration_s": params.warmup_seconds,
        "type": "warmup",
        "intensity": _INTENSITY["warmup"],
        "pace": _PACE["warmup"],
        "hr": _HR["warmup"],
        "hr_zone": _HR_ZONE["warmup"],
    })

    for i in range(1, params.intervals + 1):
        if hasattr(params, "interval_seconds"):
            dur = params.interval_seconds
        else:
            dur = int(params.interval_distance_m * 5 / 1000 * 60)

        phases.append({
            "label": f"I{i}",
            "duration_s": dur,
            "type": "interval",
            "intensity": _INTENSITY["interval"],
            "pace": _PACE["interval"],
            "hr": _HR["interval"],
            "hr_zone": _HR_ZONE["interval"],
        })

        if i < params.intervals:
            phases.append({
                "label": f"R{i}",
                "duration_s": params.recovery_seconds,
                "type": "recovery",
                "intensity": _INTENSITY["recovery"],
                "pace": _PACE["recovery"],
                "hr": _HR["recovery"],
                "hr_zone": _HR_ZONE["recovery"],
            })

    if hasattr(params, "cooldown_seconds"):
        cd_dur = params.cooldown_seconds
    else:
        cd_dur = 300

    phases.append({
        "label": "CD",
        "duration_s": cd_dur,
        "type": "cooldown",
        "intensity": _INTENSITY["cooldown"],
        "pace": _PACE["cooldown"],
        "hr": _HR["cooldown"],
        "hr_zone": _HR_ZONE["cooldown"],
    })

    return phases


def plot_workout(params: SimpleIntervalParams | AdvancedIntervalParams) -> Figure:
    """Create a 3-panel workout chart: intensity, pace, and heart rate."""
    phases = _build_phases(params)
    total_s = sum(p["duration_s"] for p in phases)

    fig, (ax_int, ax_pace, ax_hr) = plt.subplots(
        3, 1, figsize=(10, 7), sharex=True,
        gridspec_kw={"height_ratios": [2, 1, 1], "hspace": 0.08},
    )

    # Build time arrays for pace/hr step plots
    time_points = []
    pace_points = []
    hr_points = []

    x = 0.0
    for phase in phases:
        width = phase["duration_s"]
        color = _COLORS[phase["type"]]
        intensity = phase["intensity"]

        # ── Top panel: intensity bars ──
        ax_int.barh(
            y=0, width=width, left=x, height=intensity,
            color=color, edgecolor="white", linewidth=0.8, align="edge",
        )

        # Phase label with HR zone
        label_text = f"{phase['label']}\n{phase['hr_zone']}"
        ax_int.text(
            x + width / 2, intensity / 2, label_text,
            ha="center", va="center", fontsize=7, fontweight="bold", color="white",
        )

        # Pace/HR step data (start and end of each phase)
        time_points.extend([x, x + width])
        pace_points.extend([phase["pace"], phase["pace"]])
        hr_points.extend([phase["hr"], phase["hr"]])

        x += width

    # ── Top panel styling ──
    ax_int.set_yticks([0.5, 1.5, 2.5, 3.5])
    ax_int.set_yticklabels([_INTENSITY_LABELS[i] for i in [1, 2, 3, 4]], fontsize=8)
    ax_int.set_ylim(0, 4.5)
    ax_int.set_ylabel("Intensity", fontsize=9)
    for y in [1, 2, 3, 4]:
        ax_int.axhline(y=y, color="#E0E0E0", linewidth=0.5, zorder=0)
    ax_int.spines["top"].set_visible(False)
    ax_int.spines["right"].set_visible(False)

    legend_handles = [
        mpatches.Patch(color=_COLORS["warmup"], label="Warmup"),
        mpatches.Patch(color=_COLORS["interval"], label="Interval"),
        mpatches.Patch(color=_COLORS["recovery"], label="Recovery"),
        mpatches.Patch(color=_COLORS["cooldown"], label="Cooldown"),
    ]
    ax_int.legend(handles=legend_handles, loc="upper right", fontsize=7, framealpha=0.9, ncol=4)
    ax_int.set_title(params.name, fontsize=12, fontweight="bold", pad=10)

    # ── Middle panel: pace ──
    ax_pace.fill_between(time_points, pace_points, alpha=0.3, color="#FF9800", step="mid")
    ax_pace.plot(time_points, pace_points, color="#FF9800", linewidth=2, drawstyle="steps-mid")
    ax_pace.set_ylabel("Pace\n(min/km)", fontsize=9)
    ax_pace.invert_yaxis()  # Lower pace = faster, show at top
    ax_pace.grid(axis="y", alpha=0.3)
    ax_pace.spines["top"].set_visible(False)
    ax_pace.spines["right"].set_visible(False)

    # Annotate pace values at phase midpoints
    x = 0.0
    for phase in phases:
        mid = x + phase["duration_s"] / 2
        ax_pace.text(
            mid, phase["pace"] - 0.15, f"{phase['pace']:.1f}",
            ha="center", va="bottom", fontsize=7, color="#E65100", fontweight="bold",
        )
        x += phase["duration_s"]

    # ── Bottom panel: heart rate ──
    ax_hr.fill_between(time_points, hr_points, alpha=0.3, color="#E91E63", step="mid")
    ax_hr.plot(time_points, hr_points, color="#E91E63", linewidth=2, drawstyle="steps-mid")
    ax_hr.set_ylabel("Heart Rate\n(bpm)", fontsize=9)
    ax_hr.grid(axis="y", alpha=0.3)
    ax_hr.spines["top"].set_visible(False)
    ax_hr.spines["right"].set_visible(False)

    # Annotate HR values at phase midpoints
    x = 0.0
    for phase in phases:
        mid = x + phase["duration_s"] / 2
        ax_hr.text(
            mid, phase["hr"] + 2, f"{phase['hr']}",
            ha="center", va="bottom", fontsize=7, color="#880E4F", fontweight="bold",
        )
        x += phase["duration_s"]

    # HR zone bands
    ax_hr.axhspan(100, 130, alpha=0.05, color="#4CAF50", label="Z1-2")
    ax_hr.axhspan(130, 155, alpha=0.05, color="#FF9800", label="Z3")
    ax_hr.axhspan(155, 185, alpha=0.05, color="#F44336", label="Z4-5")

    # ── Shared X-axis ──
    tick_interval = 300 if total_s > 1800 else 120 if total_s > 600 else 60
    tick_positions = np.arange(0, total_s + 1, tick_interval)
    ax_hr.set_xticks(tick_positions)
    ax_hr.set_xticklabels([f"{int(t // 60)}m" for t in tick_positions], fontsize=8)
    ax_hr.set_xlim(0, total_s)
    ax_hr.set_xlabel("Time", fontsize=10)

    fig.subplots_adjust(left=0.1, right=0.95, top=0.92, bottom=0.08)
    return fig
