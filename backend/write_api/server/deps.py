"""Shared objects and helpers for write-side controllers: DB file, service clients, starting agent runs."""

from fastapi import BackgroundTasks, Request

from shared.config.llm_settings import load_llm_settings
from write_api.agent.orchestrator import AgentDeps
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.services import run_service


def db_file(request: Request):
    return request.app.state.db_file


def read_client(request: Request) -> ReadApiClient:
    return request.app.state.read_client


def supplier_client(request: Request) -> SupplierClient:
    return request.app.state.supplier_client


def agent_deps(request: Request, llm_env: str | None = None, llm_mode: str | None = None) -> AgentDeps:
    """Build the agent's dependencies from llm.env (or another env file), optionally overriding LLM_MODE."""
    settings = load_llm_settings(llm_env)
    if llm_mode:
        settings.llm_mode = llm_mode
    st = request.app.state
    return run_service.make_deps(
        db_file=st.db_file, read=st.read_client, supplier=st.supplier_client, llm_settings=settings, llm_env=llm_env
    )


def launch(
    request: Request,
    background: BackgroundTasks,
    ref: str,
    trigger_type: str,
    *,
    llm_env: str | None = None,
    llm_mode: str | None = None,
) -> tuple[str, AgentDeps]:
    """Create a run for a trigger and execute it in the background (watch it via the Read API SSE stream)."""
    deps = agent_deps(request, llm_env, llm_mode)
    run_id = run_service.start(deps, ref, trigger_type)
    background.add_task(run_service.run, deps, run_id)
    return run_id, deps
