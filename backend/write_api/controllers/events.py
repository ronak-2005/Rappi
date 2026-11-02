"""POST: external triggers. A supplier reports it can't fully deliver a PO (Scenario 2), or demand
monitoring raises an alert (Scenario 3). Each one is stored, applied, and handed to the agent."""

import uuid

from fastapi import APIRouter, BackgroundTasks, Request

from shared.db.session import read_write
from write_api.schemas.requests import DemandAlertIn, SupplierEventIn
from write_api.server.deps import launch
from write_api.services import demand_alert_service, supplier_event_service

router = APIRouter(tags=["events"])


@router.post("/supplier-events")
def supplier_event(body: SupplierEventIn, request: Request, background: BackgroundTasks):
    event_id = f"EV-{uuid.uuid4().hex[:8]}"
    with read_write(request.app.state.db_file) as s:
        supplier_event_service.create(
            s, event_id=event_id, po_id=body.po_id, confirmed_qty=body.confirmed_qty, message=body.message
        )
        supplier_event_service.apply(s, event_id, body.unavailable_days)
    out = {"event_id": event_id, "applied": True}
    if body.run_agent:
        out["run_id"], _ = launch(request, background, event_id, "supplier_event", llm_mode=body.llm_mode)
    return out


@router.post("/demand-alerts")
def demand_alert(body: DemandAlertIn, request: Request, background: BackgroundTasks):
    with read_write(request.app.state.db_file) as s:
        alert_id = demand_alert_service.create(s, node=body.node, sku=body.sku, message=body.message).id
    out = {"alert_id": alert_id}
    if body.run_agent:
        out["run_id"], _ = launch(request, background, alert_id, "demand_alert", llm_mode=body.llm_mode)
    return out
