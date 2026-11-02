"""POST: start an agent run (executes in the background; watch it via the Read API SSE stream), cancel it."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from shared.domain.errors import InvalidRequestError
from shared.domain.fixtures import load_fixture_file
from write_api.schemas.requests import StartRun
from write_api.server.deps import db_file, launch
from write_api.services import fixture_service, run_service

router = APIRouter(tags=["runs"])


@router.post("/runs")
def start_run(body: StartRun, request: Request, background: BackgroundTasks):
    st = request.app.state
    if body.fixture_id:
        fx = fixture_service.load_world(body.fixture_id, st.db_file, st.supplier_client)
    else:
        fx = load_fixture_file(st.read_client.get("/world")["fixture_id"])
    trigger_type, ref = (
        ("recommendation", body.recommendation_id) if body.recommendation_id else (fx.trigger.type, fx.trigger.ref)
    )
    if ref is None:
        raise InvalidRequestError("nothing to run: no trigger", "write_api.controllers.runs")
    run_id, deps = launch(request, background, ref, trigger_type, llm_env=body.llm_env, llm_mode=body.llm_mode)
    return {
        "run_id": run_id,
        "trigger_type": trigger_type,
        "trigger_ref": ref,
        "llm_mode": deps.llm_mode,
        "llm_model": getattr(deps.llm, "model", ""),
        "stream": f"/runs/{run_id}/stream (read_api)",
    }


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, db=Depends(db_file)):
    return run_service.cancel(db, run_id)
