"""The LLM interface the agent depends on. Messages use the OpenAI chat format
(roles: system / user / assistant with tool_calls / tool with tool_call_id)."""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    id: str
    name: str
    arguments: str  # raw JSON text as produced by the model (validated by our code, not trusted)
    extra: dict = field(default_factory=dict)  # provider-specific fields on the call; echoed back unchanged


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict = field(default_factory=dict)
    raw: dict | None = None


class LLMClient(Protocol):
    model: str

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse: ...
