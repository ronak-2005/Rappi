"""One client for every provider that speaks the OpenAI chat-completions format
(Anthropic's compatibility endpoint, OpenAI, Groq, OpenRouter, Hugging Face router, Ollama, vLLM ...).
Configured only by LLM_BASE_URL / LLM_API_KEY / LLM_MODEL."""

import logging

from openai import OpenAI

from shared.config.llm_settings import LLMSettings
from shared.domain.errors import ConfigurationError
from write_api.llm.client import LLMResponse, ToolCall

log = logging.getLogger("write_api.llm.openai_compat")


class OpenAICompatClient:
    def __init__(self, settings: LLMSettings):
        if not settings.llm_base_url or not settings.llm_model:
            raise ConfigurationError("live LLM not configured: set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in "
                                     "backend/llm.env, or run with llm_mode=baseline", "write_api.llm.openai_compat")
        self.settings = settings
        self.model = settings.llm_model
        self._client = OpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key or "none",
                              timeout=settings.llm_timeout_s,
                              max_retries=settings.llm_max_retries)  # SDK backs off on 429/5xx, honours Retry-After

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, tools=tools or None, tool_choice="auto" if tools else None,
            temperature=self.settings.llm_temperature, max_tokens=self.settings.llm_max_tokens,
        )
        msg = resp.choices[0].message
        calls = [ToolCall(id=tc.id or f"call_{i}", name=tc.function.name, arguments=tc.function.arguments or "{}")
                 for i, tc in enumerate(msg.tool_calls or [])]
        text = msg.content or ""
        if not calls and tools:
            calls = _calls_from_text(text, {t["function"]["name"] for t in tools})
            if calls:
                log.info("model wrote its tool call as text; recovered %s", [c.name for c in calls])
        usage = resp.usage.model_dump() if resp.usage else {}
        return LLMResponse(text=text, tool_calls=calls, usage=usage, raw=resp.model_dump())


def _calls_from_text(text: str, tool_names: set[str]) -> list[ToolCall]:
    """Some (often free/small) models emit a tool call as JSON in the text instead of `tool_calls`.
    Recover {"name": ..., "arguments"|"parameters": {...}} objects naming a real tool. The arguments are
    still validated by the tool registry like any other call."""
    import json
    import re
    out, decoder = [], json.JSONDecoder()
    for m in re.finditer(r"\{", text):
        try:
            obj, _ = decoder.raw_decode(text[m.start():])
        except ValueError:
            continue
        if isinstance(obj, dict) and obj.get("name") in tool_names:
            args = obj.get("arguments", obj.get("parameters", {}))
            out.append(ToolCall(id=f"textcall_{len(out)}", name=obj["name"],
                                arguments=args if isinstance(args, str) else json.dumps(args)))
    return out[:1]  # one at a time: keeps the conversation well-formed
