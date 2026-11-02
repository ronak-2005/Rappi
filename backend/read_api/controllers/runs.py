"""GET: agent runs, live trace stream (SSE), approvals and purchase orders."""

import asyncio
import json
from typing import Optional

from fastapi import APIRouter, Depends, Request
from sqlmodel import Session
from sse_starlette.sse import EventSourceResponse

from read_api.server.deps import session
from read_api.services import run_view_service as v
from shared.db.session import read_only

router = APIRouter(tags=["runs"])


@router.get("/runs")
def list_runs(s: Session = Depends(session)):
    return v.list_runs(s)


@router.get("/runs/{run_id}")
def run_detail(run_id: str, s: Session = Depends(session)):
    return v.run_detail(s, run_id)


@router.get("/runs/{run_id}/trace")
def run_trace(run_id: str, after: int = -1, s: Session = Depends(session)):
    return v.trace(s, run_id, after)


@router.get("/runs/{run_id}/stream")
async def run_stream(run_id: str, request: Request):
    """Server-sent events: each new trace step as it is written, then a final 'run' event."""
    db_file = request.app.state.db_file

    async def events():
        last, last_status = -1, None
        while True:
            if await request.is_disconnected():
                return
            with read_only(db_file) as s:
                steps = v.trace(s, run_id, last)
                detail = v.run_detail(s, run_id)
            for step in steps:
                last = step["seq"]
                yield {"event": "step", "data": json.dumps(step, default=str)}
            if steps or detail["status"] != last_status:  # only when something changed
                last_status = detail["status"]
                yield {"event": "run", "data": json.dumps(detail, default=str)}
            if detail["finished"]:
                return
            await asyncio.sleep(0.5)

    return EventSourceResponse(events())


@router.get("/approvals")
def approvals(status: Optional[str] = None, s: Session = Depends(session)):
    return v.approvals(s, status)


@router.get("/purchase-orders")
def purchase_orders(s: Session = Depends(session)):
    return v.purchase_orders(s)
