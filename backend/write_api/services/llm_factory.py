"""Build the 'brain' for a run from llm.env settings. Only this file knows the modes;
no provider names anywhere — a live model is just base_url + key + model."""

from shared.config.llm_settings import LLMSettings
from write_api.agent.baseline_policy import BaselineLLM
from write_api.llm.client import LLMClient
from write_api.llm.openai_compat import OpenAICompatClient


def build_llm(settings: LLMSettings) -> LLMClient:
    if settings.llm_mode == "live":
        return OpenAICompatClient(settings)
    return BaselineLLM()  # 'baseline' and 'scripted' both run without a key
