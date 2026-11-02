"""POST: start an agent run (executes in the background; watch it via the Read API SSE stream), cancel it."""

from fastapi import APIRouter, BackgroundTasks, Depends, Request

from shared.config.llm_settings import load_llm_settings
from shared.domain.errors import InvalidRequestError
from shared.domain.fixtures import load_fixture_file
from write_api.schemas.requests import StartRun
from write_api.server.deps import db_file
from write_api.services import fixture_service, run_service

router = APIRouter(tags=["runs"])


def deps_for(request: Request, llm_env=None, llm_mode=None):
    settings = load_llm_settings(llm_env)
    if llm_mode:
        settings.llm_mode = llm_mode
    st = request.app.state
    return run_service.make_deps(db_file=st.db_file, read=st.read_client, supplier=st.supplier_client,
                                 llm_settings=settings, llm_env=llm_env)


@router.post("/runs")
def start_run(body: StartRun, request: Request, background: BackgroundTasks):
    st = request.app.state
    rec_id = body.recommendation_id
    if body.fixture_id:
        fx = fixture_service.load_world(body.fixture_id, st.db_file, st.supplier_client)
        rec_id = rec_id or (fx.trigger.recommendation.id if fx.trigger.recommendation else None)
    if rec_id is None:
        world = st.read_client.get("/world")
        fx = load_fixture_file(world["fixture_id"])
        rec_id = fx.trigger.recommendation.id if fx.trigger.recommendation else None
    if rec_id is None:
        raise InvalidRequestError("no recommendation to review", "write_api.controllers.runs")
    deps = deps_for(request, body.llm_env, body.llm_mode)
    run_id = run_service.start(deps, rec_id)
    background.add_task(run_service.run, deps, run_id)
    return {"run_id": run_id, "recommendation_id": rec_id, "llm_mode": deps.llm_mode,
            "llm_model": getattr(deps.llm, "model", ""), "stream": f"/runs/{run_id}/stream (read_api)"}


@router.post("/runs/{run_id}/cancel")
def cancel(run_id: str, db=Depends(db_file)):
    return run_service.cancel(db, run_id)
