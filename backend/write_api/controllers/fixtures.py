"""POST: load a scenario world (replaces all data) and configure the mock supplier for it."""

from fastapi import APIRouter, Depends

from shared.domain.errors import NotFoundError
from write_api.clients.supplier_client import SupplierClient
from write_api.server.deps import db_file, supplier_client
from write_api.services import fixture_service

router = APIRouter(tags=["fixtures"])


@router.post("/fixtures/{fixture_id}/load")
def load(fixture_id: str, db=Depends(db_file), supplier: SupplierClient = Depends(supplier_client)):
    try:
        fx = fixture_service.load_world(fixture_id, db, supplier)
    except FileNotFoundError as exc:
        raise NotFoundError("fixture", fixture_id, "write_api.controllers.fixtures") from exc
    rec = fx.trigger.recommendation
    return {"loaded": fx.id, "today": fx.today.isoformat(), "recommendation_id": rec.id if rec else None}
