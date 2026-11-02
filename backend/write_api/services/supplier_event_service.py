"""Use-case (Scenario 2): a supplier tells us it can't fully deliver a PO.

Applies the facts to the database (PO confirmed qty + status, an event on the PO, and a supplier
availability limit so nobody re-orders from it), then the agent decides what to do about the gap.
"""

from sqlmodel import Session

from shared.db import models as m
from shared.db import snapshot
from shared.domain.errors import NotFoundError
from write_api.repositories import availability_repository, order_repository


def apply(session: Session, event_id: str, unavailable_days: int = 14) -> m.SupplierEvent:
    ev = session.get(m.SupplierEvent, event_id)
    if ev is None:
        raise NotFoundError("supplier_event", event_id, "write_api.services.supplier_event_service")
    po = session.get(m.PurchaseOrder, ev.po_id)
    if po is None:
        raise NotFoundError("purchase_order", ev.po_id, "write_api.services.supplier_event_service")
    status = (
        "rejected"
        if ev.confirmed_qty == 0
        else ("partially_confirmed" if ev.confirmed_qty < po.qty_ordered else "confirmed")
    )
    order_repository.update_po(session, po, qty_confirmed=ev.confirmed_qty, status=status, notes=ev.message)
    order_repository.add_event(
        session, po.id, status, {"supplier_event": ev.id, "message": ev.message, "confirmed_qty": ev.confirmed_qty}
    )
    if ev.confirmed_qty < po.qty_ordered:
        availability_repository.record_unavailable(
            session, ev.supplier_id, ev.sku_id, snapshot.world(session).today, unavailable_days, ev.message
        )
    return ev


def create(session: Session, *, event_id: str, po_id: str, confirmed_qty: int, message: str) -> m.SupplierEvent:
    """Webhook entry point: store a new supplier event (then call apply)."""
    po = session.get(m.PurchaseOrder, po_id)
    if po is None:
        raise NotFoundError("purchase_order", po_id, "write_api.services.supplier_event_service")
    ev = m.SupplierEvent(
        id=event_id,
        po_id=po_id,
        supplier_id=po.supplier_id,
        node_id=po.node_id,
        sku_id=po.sku_id,
        confirmed_qty=confirmed_qty,
        message=message,
        received_on=snapshot.world(session).today,
    )
    session.add(ev)
    session.commit()
    return ev
