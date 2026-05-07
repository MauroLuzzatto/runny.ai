from __future__ import annotations

import json
import logging
import time
from collections.abc import Generator

import streamlit as st

from openai import OpenAI
from garminconnect.workout import RunningWorkout

from core.models import Activities, UserProfile
from core.prompts import build_system_prompt
from core.schemas import (
    SimpleIntervalParams,
    SteadyRunParams,
    TrainingPlan,
    build_workout_from_params,
)

logger = logging.getLogger("runny.coach")


DEFAULT_MODEL = "anthropic/claude-sonnet-4-6"
MAX_RETRIES = 3

WORKOUT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_simple_interval_workout",
            "description": (
                "Create a time-based interval workout (e.g. 5x4min intervals). "
                "Use for workouts with repeated work/recovery blocks defined by duration."
            ),
            "parameters": SimpleIntervalParams.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_steady_run",
            "description": (
                "Create a steady-pace run: warmup → main run at target pace → cooldown. "
                "Use for easy runs, long runs, tempo runs, or any workout WITHOUT "
                "intervals or recovery blocks. Set recovery_seconds=0 is NOT needed — "
                "use this tool instead."
            ),
            "parameters": SteadyRunParams.model_json_schema(),
        },
    },
]

ANALYSIS_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_training_plan",
            "description": (
                "Save the weekly training plan you just recommended. "
                "Call this AFTER presenting the plan table in your response. "
                "Include every session from the table (including rest days)."
            ),
            "parameters": TrainingPlan.model_json_schema(),
        },
    },
]

ALL_TOOLS = ANALYSIS_TOOLS + WORKOUT_TOOLS


class RunningCoach:
    """AI running coach that maintains a single continuous conversation.

    Mode (analysis/workout/feedback) controls which tools are available
    but the conversation history is never reset — prior context carries forward.
    """

    def __init__(
        self,
        activities: Activities | None = None,
        profile: UserProfile | None = None,
    ) -> None:
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=st.session_state.get("openrouter_key")
            or st.secrets.get("OPENROUTER_KEY"),
        )
        self.activities = activities
        self.profile = profile
        self.training_summary: str | None = None
        self.training_plan: TrainingPlan | None = None
        self._mode: str = "analysis"
        self.messages: list[dict] = [
            {"role": "system", "content": build_system_prompt(activities, profile)},
        ]

    @property
    def mode(self) -> str:
        return self._mode

    def switch_mode(self, mode: str) -> None:
        """Switch the active mode. Conversation history is preserved."""
        self._mode = mode

    def update_activities(self, activities: Activities) -> None:
        """Update activities and rebuild the system prompt."""
        self.activities = activities
        self.messages[0] = {
            "role": "system",
            "content": build_system_prompt(activities, self.profile),
        }

    def update_profile(self, profile: UserProfile) -> None:
        """Update profile and rebuild the system prompt."""
        self.profile = profile
        self.messages[0] = {
            "role": "system",
            "content": build_system_prompt(self.activities, profile),
        }

    def chat(
        self, user_message: str
    ) -> tuple[
        str, RunningWorkout | None, SimpleIntervalParams | SteadyRunParams | None
    ]:
        """Non-streaming chat. Returns (text, workout, params)."""
        self.messages.append({"role": "user", "content": user_message})

        workout = None
        workout_params = None

        for _ in range(5):
            response = self._call_api(stream=False)
            choice = response.choices[0]
            message = choice.message

            self.messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                text = message.content or ""
                if self._mode == "analysis":
                    self.training_summary = text
                return text, workout, workout_params

            workout, workout_params = self._handle_tool_calls(message.tool_calls)

        return self.messages[-1].get("content", ""), workout, workout_params

    def chat_stream(
        self, user_message: str
    ) -> Generator[
        str | tuple[RunningWorkout, SimpleIntervalParams | SteadyRunParams],
        None,
        None,
    ]:
        """Streaming chat. Yields text chunks, then optionally a (workout, params) tuple."""
        self.messages.append({"role": "user", "content": user_message})

        workout_created = False

        for _ in range(5):
            stream = self._call_api(stream=True)

            full_content = ""
            tool_calls_data: dict[int, dict] = {}

            for chunk in stream:
                delta = chunk.choices[0].delta

                # Text content
                if delta.content:
                    full_content += delta.content
                    yield delta.content

                # Tool call chunks
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_data:
                            tool_calls_data[idx] = {
                                "id": tc.id or "",
                                "function": {"name": "", "arguments": ""},
                            }
                        if tc.id:
                            tool_calls_data[idx]["id"] = tc.id
                        if tc.function:
                            if tc.function.name:
                                tool_calls_data[idx]["function"]["name"] = (
                                    tc.function.name
                                )
                            if tc.function.arguments:
                                tool_calls_data[idx]["function"]["arguments"] += (
                                    tc.function.arguments
                                )

            # Append assistant message to history
            assistant_msg: dict = {"role": "assistant", "content": full_content or None}
            if tool_calls_data:
                assistant_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function", "function": tc["function"]}
                    for tc in tool_calls_data.values()
                ]
            self.messages.append(assistant_msg)

            # No tool calls
            if not tool_calls_data:
                if workout_created:
                    # Workout already built — this text is the summary, we're done
                    return
                if self._mode == "analysis":
                    self.training_summary = full_content
                    # Force save_training_plan tool call
                    tool_calls_data = self._force_tool_call(
                        nudge="Save the training plan you just recommended by calling save_training_plan."
                    )
                    if not tool_calls_data:
                        return
                elif self._mode == "workout":
                    # In workout mode: force a workout tool call
                    tool_calls_data = self._force_tool_call()
                    if not tool_calls_data:
                        return
                else:
                    # Feedback mode: no tools, just return text
                    return

            # Handle tool calls
            workout, params = self._handle_tool_calls_from_dicts(tool_calls_data)
            if workout:
                yield (workout, params)
                workout_created = True
                # Continue loop so the LLM can describe the workout it just created

    def _force_tool_call(
        self, nudge: str = "Now create the workout based on what you just described."
    ) -> dict[int, dict]:
        """Force the LLM to produce a tool call based on the conversation so far.

        Makes a non-streaming API call with tool_choice='required' so the model
        must call one of the available tools. Returns tool_calls_data dict
        in the same format as the streaming parser, or empty dict on failure.
        """
        logger.info("Forcing tool call: %s", nudge[:60])
        self.messages.append({"role": "user", "content": nudge})
        try:
            response = self._call_api(stream=False, force_tool=True)
            message = response.choices[0].message
            self.messages.append(message.model_dump(exclude_none=True))

            if not message.tool_calls:
                return {}

            return {
                i: {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for i, tc in enumerate(message.tool_calls)
            }
        except Exception:
            return {}

    def _handle_tool_calls(
        self, tool_calls
    ) -> tuple[RunningWorkout | None, SimpleIntervalParams | SteadyRunParams | None]:
        """Process tool calls from a non-streaming response."""
        workout = None
        workout_params = None

        for tool_call in tool_calls:
            fn_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            workout, workout_params = self._execute_tool(fn_name, args, tool_call.id)

        return workout, workout_params

    def _handle_tool_calls_from_dicts(
        self, tool_calls_data: dict[int, dict]
    ) -> tuple[RunningWorkout | None, SimpleIntervalParams | SteadyRunParams | None]:
        """Process tool calls from streaming chunks."""
        workout = None
        workout_params = None

        for tc in tool_calls_data.values():
            fn_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            workout, workout_params = self._execute_tool(fn_name, args, tc["id"])

        return workout, workout_params

    def _execute_tool(
        self, fn_name: str, args: dict, tool_call_id: str
    ) -> tuple[RunningWorkout | None, SimpleIntervalParams | SteadyRunParams | None]:
        """Execute a single tool call and append the result to messages."""
        if fn_name == "save_training_plan":
            plan = TrainingPlan(**args)
            self.training_plan = plan
            logger.info(
                "Training plan saved: %d sessions, ~%.0f km",
                len(plan.sessions),
                plan.total_km,
            )
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps(
                        {"status": "saved", "sessions": len(plan.sessions)}
                    ),
                }
            )
            return None, None

        if fn_name == "create_simple_interval_workout":
            params = SimpleIntervalParams(**args)
        elif fn_name == "create_steady_run":
            params = SteadyRunParams(**args)
        else:
            self.messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call_id,
                    "content": json.dumps({"error": f"Unknown tool: {fn_name}"}),
                }
            )
            return None, None

        workout = build_workout_from_params(params)
        self.messages.append(
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps(
                    {
                        "status": "success",
                        "workout_name": params.name,
                        "parameters": params.model_dump(),
                    }
                ),
            }
        )
        return workout, params

    def _call_api(self, stream: bool = False, force_tool: bool = False):
        """Call the OpenRouter API with retry logic."""
        kwargs: dict = {
            "model": st.session_state.get("openrouter_model", DEFAULT_MODEL),
            "messages": self.messages,
            "stream": stream,
        }
        if self._mode == "workout":
            kwargs["tools"] = WORKOUT_TOOLS
            kwargs["tool_choice"] = "required" if force_tool else "auto"
        elif self._mode == "analysis":
            kwargs["tools"] = ALL_TOOLS
            kwargs["tool_choice"] = "required" if force_tool else "auto"
        # feedback mode: no tools

        for attempt in range(MAX_RETRIES):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2**attempt)
                else:
                    raise
