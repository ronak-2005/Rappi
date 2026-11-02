"""GET /health (service up) and GET /health/llm (does the configured LLM endpoint support tool calls?)."""

from fastapi import APIRouter, Request

from shared.config.llm_settings import load_llm_settings
from write_api.services import run_service

router = APIRouter(tags=["health"])


@router.get("/health")
def health(request: Request):
    s = load_llm_settings()
    return {"service": "write_api", "ok": True, "llm_mode": s.llm_mode, "llm_model": s.llm_model}


@router.get("/health/llm")
def health_llm(env: str | None = None):
    return run_service.llm_health(load_llm_settings(env))
