"""ScriptedLLM: replays a fixed list of responses. Used by tests to drive the orchestrator through
exact paths (missing evidence, invalid JSON, rulebook rejection ...) at zero cost."""

import json
from typing import Callable, Union

from write_api.llm.client import LLMResponse, ToolCall

Step = Union[LLMResponse, Callable[[list[dict]], LLMResponse]]


def call(name: str, args: dict | str | None = None, id_: str | None = None) -> LLMResponse:
    raw = args if isinstance(args, str) else json.dumps(args or {})
    return LLMResponse(tool_calls=[ToolCall(id=id_ or f"call_{name}", name=name, arguments=raw)])


class ScriptedLLM:
    model = "scripted"

    def __init__(self, steps: list[Step]):
        self.steps = list(steps)
        self.calls = 0

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        if self.calls >= len(self.steps):
            return LLMResponse(text="(script exhausted)")
        step = self.steps[self.calls]
        self.calls += 1
        return step(messages) if callable(step) else step
