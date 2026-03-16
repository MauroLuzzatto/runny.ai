# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What is this project?

**runny.ai** is a Streamlit-based AI running coach that connects to Garmin Connect, fetches training history, and generates personalized running workouts using Claude (via OpenRouter). Generated workouts can be uploaded and scheduled directly to Garmin Connect.

## Commands

```bash
# Install dependencies (uses uv, Python 3.13)
uv sync

# Run the app
uv run streamlit run app.py

# Run with env vars from .env
# Required: OPENROUTER_KEY, GARMIN_EMAIL, GARMIN_PASSWORD
```

No test suite exists yet.

## Architecture

### Data flow

1. **Garmin Connect** (`core/client.py`, `core/fetch.py`) — authenticates via `garminconnect` library, fetches activities as raw dicts
2. **Pydantic models** (`core/models.py`) — `Activity` and `Activities` validate and normalize Garmin API responses. `Activities` has query helpers (`.runs()`, `.by_sport()`, `.fastest_pace()`, etc.)
3. **AI coach** (`core/ai_assistant.py`) — `RunningCoach` class wraps OpenAI-compatible chat (pointed at OpenRouter) with tool-use. Uses streaming. Automatically routes to Sonnet for workout generation and Haiku for conversation (model selection happens in `app.py:_pick_model`)
4. **Tool execution** — The LLM calls either `create_simple_interval_workout` (time-based) or `create_advanced_interval_workout` (distance-based with pace/HR targets). Tool schemas are derived from Pydantic models in `core/schemas.py`
5. **Workout building** (`core/workouts.py`) — constructs `garminconnect.workout.RunningWorkout` objects using the library's step builders
6. **Visualization** (`core/plotting.py`) — matplotlib 3-panel chart (intensity bars, pace, heart rate) rendered in the Streamlit right column
7. **Upload/Schedule** (`core/workouts.py`) — uploads workouts to Garmin Connect and optionally schedules them on a date

### Key design decisions

- LLM calls go through **OpenRouter** (`https://openrouter.ai/api/v1`), not directly to Anthropic. Models are referenced as `anthropic/claude-sonnet-4-6` and `anthropic/claude-haiku-4-5`.
- The system prompt (`core/prompts.py`) injects recent run summaries so the LLM has training context. It mandates a specific response format (markdown table with phases, pace, HR zones, training effect estimates).
- Workouts flow through the chat as tool calls: LLM decides parameters → tool builds `RunningWorkout` → result sent back to LLM for summary → workout object stored in `st.session_state.pending_workouts` for the user to review/upload.
- `app.py` uses a two-column layout: chat on the left, workout generator controls and proposed workouts on the right (sticky).

### Environment variables (`.env`)

- `OPENROUTER_KEY` — API key for OpenRouter
- `GARMIN_EMAIL` / `GARMIN_PASSWORD` — Garmin Connect credentials

### Reference docs

`docs/DOCS.md` contains the Garmin Workout API reference (step types, end conditions, target types, pace conversion). Consult this when modifying workout construction logic.

`ideas/SUGGESTIONS.md` describes a planned rule-based training suggestion feature (zone + structure model) that is not yet integrated into the main app.
