"""Use-cases around agent runs: start a run, resolve an approval and resume, LLM health check."""

import json
import logging
from typing import Optional

from shared.config.llm_settings import LLMSettings, load_llm_settings
from shared.config.policy import get_policy
from shared.config.settings import get_settings
from shared.db.session import read_write
from shared.domain.errors import ConflictError, InvalidRequestError
from write_api.actions import approvals
from write_api.agent.orchestrator import AgentDeps, Approver, Orchestrator
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.repositories import run_repository as runs
from write_api.services.llm_factory import build_llm

log = logging.getLogger("write_api.services.run_service")


def make_deps(*, db_file: Optional[str], read: ReadApiClient, supplier: SupplierClient,
              llm_settings: Optional[LLMSettings] = None, approver: Optional[Approver] = None,
              llm_env: Optional[str] = None) -> AgentDeps:
    settings = llm_settings or load_llm_settings(llm_env)
    return AgentDeps(llm=build_llm(settings), llm_mode=settings.llm_mode, read=read, supplier=supplier,
                     policy=get_policy(), db_file=db_file, approver=approver,
                     trace_dir=get_settings().var_dir / "runs", llm_env=llm_env)


def run_llm_config(db_file: Optional[str], run_id: str) -> tuple[Optional[str], str]:
    """(llm_env, llm_mode) a run was started with, so it resumes with the same brain."""
    with read_write(db_file) as s:
        run = runs.get_run(s, run_id)
        return run.memory.get("llm_env"), run.llm_mode


def start(deps: AgentDeps, trigger_ref: str, trigger_type: str = "recommendation") -> str:
    return Orchestrator(deps).start(trigger_ref, trigger_type)


def run(deps: AgentDeps, run_id: str):
    return Orchestrator(deps).run(run_id)


def approval_run_id(db_file: Optional[str], approval_id: str) -> str:
    with read_write(db_file) as s:
        a = runs.get_approval(s, approval_id)
        if a is None:
            from shared.domain.errors import NotFoundError
            raise NotFoundError("approval", approval_id, "write_api.services.run_service")
        return a.run_id


def resolve_approval(deps: AgentDeps, approval_id: str, decision: str, by: str, comment: str,
                     edited_lines: Optional[list[dict]]) -> str:
    if decision not in ("approve", "reject", "edit"):
        raise InvalidRequestError("decision must be approve | reject | edit", "write_api.services.run_service")
    if decision == "edit" and not edited_lines:
        raise InvalidRequestError("an edit needs the new order lines", "write_api.services.run_service")
    with read_write(deps.db_file) as s:
        a = approvals.resolve(s, approval_id, decision, by, comment, edited_lines)
        run = runs.get_run(s, a.run_id)
        if run.status != "awaiting_approval":
            raise ConflictError(f"run {run.id} is {run.status}, not awaiting approval", "write_api.services.run_service")
    return a.run_id


def resume(deps: AgentDeps, run_id: str):
    return Orchestrator(deps).resume(run_id)


def cancel(db_file: Optional[str], run_id: str) -> dict:
    with read_write(db_file) as s:
        run = runs.get_run(s, run_id)
        if run.status in ("completed", "escalated", "failed", "cancelled"):
            raise ConflictError(f"run {run_id} already {run.status}", "write_api.services.run_service")
        runs.update_run(s, run, status="cancelled", state="CANCELLED")
        runs.add_step(s, run_id, "CANCELLED", "info", "cancelled", {"by": "user"})
    return {"run_id": run_id, "status": "cancelled"}


def llm_health(settings: Optional[LLMSettings] = None) -> dict:
    """Send a tiny tool-call test to the configured endpoint: proves the env works before a real run."""
    settings = settings or load_llm_settings()
    info = {"mode": settings.llm_mode, "base_url": settings.llm_base_url, "model": settings.llm_model,
            "api_key_set": bool(settings.llm_api_key)}
    if settings.llm_mode != "live":
        return {**info, "ok": True, "tools_supported": True, "note": "no LLM call in this mode"}
    try:
        llm = build_llm(settings)
        tool = {"type": "function", "function": {"name": "ping", "description": "Reply by calling this tool.",
                                                 "parameters": {"type": "object", "properties": {
                                                     "ok": {"type": "boolean"}}, "required": ["ok"]}}}
        resp = llm.chat([{"role": "user", "content": "Call the ping tool with ok=true."}], [tool])
        called = [t.name for t in resp.tool_calls]
        args = json.loads(resp.tool_calls[0].arguments) if resp.tool_calls else None
        return {**info, "ok": True, "tools_supported": "ping" in called, "reply": {"tool_calls": called, "args": args,
                                                                                   "text": resp.text[:200]}}
    except Exception as exc:
        log.warning("LLM health check failed: %s", exc)
        return {**info, "ok": False, "tools_supported": False, "error": f"{type(exc).__name__}: {exc}"}
