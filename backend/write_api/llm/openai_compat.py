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
                              timeout=settings.llm_timeout_s, max_retries=2)

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        resp = self._client.chat.completions.create(
            model=self.model, messages=messages, tools=tools or None, tool_choice="auto" if tools else None,
            temperature=self.settings.llm_temperature, max_tokens=self.settings.llm_max_tokens,
        )
        msg = resp.choices[0].message
        calls = [ToolCall(id=tc.id, name=tc.function.name, arguments=tc.function.arguments or "{}")
                 for tc in (msg.tool_calls or [])]
        usage = resp.usage.model_dump() if resp.usage else {}
        return LLMResponse(text=msg.content or "", tool_calls=calls, usage=usage, raw=resp.model_dump())
