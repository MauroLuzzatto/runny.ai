# Running Training Suggestion UI — Concept Summary

## Overview

A lightweight decision-support tool that takes a small set of user inputs (fatigue, recent training load, weekly volume, goal) and surfaces a **single recommended training session** with a short rationale, plus 2–3 alternatives ranked by suitability. The goal is to reduce decision fatigue — not present a menu.

---

## Data Model

Two core concepts, each orthogonal:

### Zone (intensity)

| ID  | Name       | HR % of max | Feel                    |
|-----|------------|-------------|-------------------------|
| Z1  | Recovery   | 60–70%      | Trivially easy          |
| Z2  | Aerobic    | 70–80%      | Conversational          |
| Z3  | Tempo      | 80–88%      | Comfortably hard        |
| Z4  | Threshold  | 88–92%      | Hard, ~20–40 min max    |
| Z5  | VO₂max     | 92–100%     | Near max, short bursts  |

### Structure (session format)

`continuous` · `intervals` · `progression` · `fartlek` · `hills` · `rest`

Any session is fully described by `(zone, structure)`. For example:
- Z3 + continuous = tempo run
- Z3 + intervals = cruise intervals
- Z5 + intervals = VO₂max repeats
- Z2 + fartlek = easy fartlek

---

## Session Catalogue

Each session entry carries:

```python
{
    "name": str,
    "zone": str,              # Z1–Z5 key
    "structure": str,         # one of the structure types above
    "duration_min": int,
    "load": str,              # "Low" | "Medium" | "High"
    "description": str,       # 1–2 sentence user-facing blurb
    "conditions": Callable,   # (inputs: dict) -> bool  — when to recommend this
    "reason": Callable,       # (inputs: dict) -> str   — personalised "why" text
}
```

The current catalogue contains 8 sessions: easy run, long run, tempo run, cruise intervals, VO₂max intervals, hill repeats, easy fartlek, rest day.

---

## Inputs

| Input              | Type    | Range / Values                                              |
|--------------------|---------|-------------------------------------------------------------|
| `days_hard`        | int     | 0–7 — days since last Z4/Z5 effort                         |
| `weekly_km`        | float   | km run so far this week                                     |
| `target_km`        | float   | weekly volume target                                        |
| `fatigue`          | int     | 1 (fresh) to 5 (cooked)                                     |
| `goal`             | str     | one of 4 training goals (see below)                        |
| `day_of_week`      | str     | derived from system date; used to detect weekend long-run window |

**Training goals:**
- Build aerobic base
- Raise lactate threshold
- Improve race speed
- Build strength & power

---

## Recommendation Logic

```
1. Evaluate conditions(inputs) for every session in the catalogue → bool
2. Collect all matching sessions → `candidates`
3. primary   = candidates[0]          (first match wins — order in catalogue matters)
4. alts      = candidates[1:] + non-matching[:N] capped at 3
5. Fallback  = "easy run" if candidates is empty
```

The ordering of the catalogue encodes priority implicitly. Sessions earlier in the list are preferred when multiple match. The current priority is:

```
easy run → long run → tempo → cruise intervals → VO₂max → hills → fartlek → rest
```

Adjust this order (or add scoring weights) as the logic becomes more sophisticated.

---

## UI Structure

```
┌─────────────────────────────────────┐
│  Inputs                             │  ← slider / selectbox / number_input
│  days_hard · fatigue · weekly_km    │
│  target_km · goal                   │
├─────────────────────────────────────┤
│  Recommended session        [card]  │
│  ┌ zone badge ┐ ┌ structure badge ┐ │
│  Session name                       │
│  Description                        │
│  Duration · HR target · Load        │
│  ─────────────────────────────────  │
│  Why this?  <personalised reason>   │
│  [ Plan this session → ]            │
└─────────────────────────────────────┘
│  Or try instead                     │
│  ┌─── alt 1 ──────────────[Select]─┐│
│  ┌─── alt 2 ──────────────[Select]─┐│
│  ┌─── alt 3 ──────────────[Select]─┐│
└─────────────────────────────────────┘
```

Each alternative card shows: zone badge, structure badge, name, duration + feel + load, and a Select button.

---

## Extension Points

### Connect to Garmin data
Replace manual sliders with values derived from `.fit` file parsing:
- `days_hard` ← scan recent activities for last session with avg HR > Z4 threshold
- `fatigue` ← compute from HRV trend or training load score (Garmin provides both)
- `weekly_km` ← sum of activity distances since Monday

### Add periodisation awareness
Add a `weeks_to_race` input. As the race approaches, shift the catalogue priority toward race-specific sessions (Z4/Z5 intervals) and reduce long easy volume.

### Logging & history
Record which session the user selects each day. Use this to:
- Detect patterns (e.g. user always skips intervals → surface them more gently)
- Display a weekly training load chart
- Enforce recovery rules (e.g. no two Z5 sessions within 48 h)

### Scoring weights (future)
Replace the binary `conditions` bool with a numeric score per session. Rank by score descending. This allows partial matches and smoother degradation when no session fits cleanly.

---

## Files

| File                       | Purpose                              |
|----------------------------|--------------------------------------|
| `running_suggestions.py`   | Streamlit app — all logic and UI     |

The app is a single file with no external dependencies beyond `streamlit`. No database, no authentication, no API calls required to run.