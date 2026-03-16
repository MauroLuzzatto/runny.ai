from __future__ import annotations

import json
import os
import time
from collections.abc import Generator

from dotenv import load_dotenv
from openai import OpenAI
from garminconnect.workout import RunningWorkout

from core.models import Activities
from core.prompts import build_system_prompt
from core.schemas import (
    AdvancedIntervalParams,
    SimpleIntervalParams,
    build_workout_from_params,
)

load_dotenv()

MODEL_SONNET = "anthropic/claude-sonnet-4-6"
MODEL_HAIKU = "anthropic/claude-haiku-4-5"
MAX_RETRIES = 3

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "create_simple_interval_workout",
            "description": (
                "Create a simple time-based interval workout. Use this for workouts "
                "where intervals are defined by duration (seconds) rather than distance."
            ),
            "parameters": SimpleIntervalParams.model_json_schema(),
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_advanced_interval_workout",
            "description": (
                "Create a distance-based interval workout with pace and HR targets. "
                "Use this for workouts where intervals are defined by distance (meters)."
            ),
            "parameters": AdvancedIntervalParams.model_json_schema(),
        },
    },
]


class RunningCoach:
    """AI running coach that creates personalized workouts via tool-use chat."""

    def __init__(
        self, activities: Activities | None = None, model: str = MODEL_SONNET
    ) -> None:
        self.client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=os.getenv("OPENROUTER_KEY"),
        )
        self.model = model
        self.messages: list[dict] = [
            {"role": "system", "content": build_system_prompt(activities)},
        ]

    def set_model(self, model: str) -> None:
        """Switch between Sonnet and Haiku."""
        self.model = model

    def update_activities(self, activities: Activities) -> None:
        """Rebuild the system prompt with fresh activity data."""
        self.messages[0] = {
            "role": "system",
            "content": build_system_prompt(activities),
        }

    def chat(
        self, user_message: str
    ) -> tuple[str, RunningWorkout | None, SimpleIntervalParams | AdvancedIntervalParams | None]:
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
                return message.content or "", workout, workout_params

            workout, workout_params = self._handle_tool_calls(message.tool_calls)

        return self.messages[-1].get("content", ""), workout, workout_params

    def chat_stream(
        self, user_message: str
    ) -> Generator[str | tuple[RunningWorkout, SimpleIntervalParams | AdvancedIntervalParams], None, None]:
        """Streaming chat. Yields text chunks, then optionally a (workout, params) tuple."""
        self.messages.append({"role": "user", "content": user_message})

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
                                tool_calls_data[idx]["function"]["name"] = tc.function.name
                            if tc.function.arguments:
                                tool_calls_data[idx]["function"]["arguments"] += tc.function.arguments

            # Append assistant message to history
            assistant_msg: dict = {"role": "assistant", "content": full_content or None}
            if tool_calls_data:
                assistant_msg["tool_calls"] = [
                    {"id": tc["id"], "type": "function", "function": tc["function"]}
                    for tc in tool_calls_data.values()
                ]
            self.messages.append(assistant_msg)

            # No tool calls — done
            if not tool_calls_data:
                return

            # Handle tool calls and loop for the summary
            workout, params = self._handle_tool_calls_from_dicts(tool_calls_data)
            if workout:
                yield (workout, params)

    def _handle_tool_calls(self, tool_calls) -> tuple[RunningWorkout | None, SimpleIntervalParams | AdvancedIntervalParams | None]:
        """Process tool calls from a non-streaming response."""
        workout = None
        workout_params = None

        for tool_call in tool_calls:
            fn_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)
            workout, workout_params = self._execute_tool(fn_name, args, tool_call.id)

        return workout, workout_params

    def _handle_tool_calls_from_dicts(self, tool_calls_data: dict[int, dict]) -> tuple[RunningWorkout | None, SimpleIntervalParams | AdvancedIntervalParams | None]:
        """Process tool calls from streaming chunks."""
        workout = None
        workout_params = None

        for tc in tool_calls_data.values():
            fn_name = tc["function"]["name"]
            args = json.loads(tc["function"]["arguments"])
            workout, workout_params = self._execute_tool(fn_name, args, tc["id"])

        return workout, workout_params

    def _execute_tool(self, fn_name: str, args: dict, tool_call_id: str) -> tuple[RunningWorkout | None, SimpleIntervalParams | AdvancedIntervalParams | None]:
        """Execute a single tool call and append the result to messages."""
        if fn_name == "create_simple_interval_workout":
            params = SimpleIntervalParams(**args)
        elif fn_name == "create_advanced_interval_workout":
            params = AdvancedIntervalParams(**args)
        else:
            self.messages.append({
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": json.dumps({"error": f"Unknown tool: {fn_name}"}),
            })
            return None, None

        workout = build_workout_from_params(params)
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": json.dumps({
                "status": "success",
                "workout_name": params.name,
                "parameters": params.model_dump(),
            }),
        })
        return workout, params

    def _call_api(self, stream: bool = False):
        """Call the OpenRouter API with retry logic."""
        for attempt in range(MAX_RETRIES):
            try:
                return self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages,
                    tools=TOOLS,
                    stream=stream,
                    max_tokens=2048,
                )
            except Exception:
                if attempt < MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise
