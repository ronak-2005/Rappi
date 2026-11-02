"""POST: a human approves, rejects or edits a plan that broke a soft rule; the run then resumes."""

from fastapi import APIRouter, BackgroundTasks, Request

from write_api.controllers.runs import deps_for
from write_api.schemas.requests import ResolveApproval
from write_api.services import run_service

router = APIRouter(tags=["approvals"])


@router.post("/approvals/{approval_id}")
def resolve(approval_id: str, body: ResolveApproval, request: Request, background: BackgroundTasks):
    original = run_service.approval_run_id(request.app.state.db_file, approval_id)
    llm_env, llm_mode = run_service.run_llm_config(request.app.state.db_file, original)
    deps = deps_for(request, llm_env, llm_mode)
    run_id = run_service.resolve_approval(deps, approval_id, body.decision, body.by, body.comment, body.lines)
    background.add_task(run_service.resume, deps, run_id)
    return {"approval_id": approval_id, "decision": body.decision, "run_id": run_id, "resuming": True}
