"""POST: external triggers. A supplier reports it can't fully deliver a PO (Scenario 2), or demand
monitoring raises an alert (Scenario 3). Each one is stored, applied, and handed to the agent."""

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, BackgroundTasks, Request
from pydantic import BaseModel

from shared.db import models as m
from shared.db import snapshot
from shared.db.session import read_write
from write_api.controllers.runs import deps_for
from write_api.services import run_service, supplier_event_service

router = APIRouter(tags=["events"])


class SupplierEventIn(BaseModel):
    po_id: str
    confirmed_qty: int
    message: str
    unavailable_days: int = 14
    run_agent: bool = True
    llm_mode: Optional[Literal["live", "baseline", "scripted"]] = None


class DemandAlertIn(BaseModel):
    node: str
    sku: str
    message: str
    run_agent: bool = True
    llm_mode: Optional[Literal["live", "baseline", "scripted"]] = None


@router.post("/supplier-events")
def supplier_event(body: SupplierEventIn, request: Request, background: BackgroundTasks):
    st = request.app.state
    event_id = f"EV-{uuid.uuid4().hex[:8]}"
    with read_write(st.db_file) as s:
        supplier_event_service.create(s, event_id=event_id, po_id=body.po_id, confirmed_qty=body.confirmed_qty,
                                      message=body.message)
        supplier_event_service.apply(s, event_id, body.unavailable_days)
    out = {"event_id": event_id, "applied": True}
    if body.run_agent:
        deps = deps_for(request, None, body.llm_mode)
        out["run_id"] = run_service.start(deps, event_id, "supplier_event")
        background.add_task(run_service.run, deps, out["run_id"])
    return out


@router.post("/demand-alerts")
def demand_alert(body: DemandAlertIn, request: Request, background: BackgroundTasks):
    st = request.app.state
    alert_id = f"AL-{uuid.uuid4().hex[:8]}"
    with read_write(st.db_file) as s:
        s.add(m.DemandAlert(id=alert_id, node_id=body.node, sku_id=body.sku, message=body.message,
                            raised_on=snapshot.world(s).today))
        s.commit()
    out = {"alert_id": alert_id}
    if body.run_agent:
        deps = deps_for(request, None, body.llm_mode)
        out["run_id"] = run_service.start(deps, alert_id, "demand_alert")
        background.add_task(run_service.run, deps, out["run_id"])
    return out
