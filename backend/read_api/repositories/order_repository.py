"""SELECT-only access to purchase orders, their events and transfers."""

from sqlmodel import Session, select

from shared.db import models as m

OPEN = ("draft", "pending_approval", "sent", "confirmed", "partially_confirmed")


def purchase_orders(
    session: Session,
    node_id: str | None = None,
    sku_id: str | None = None,
    only_open: bool = False,
    run_id: str | None = None,
) -> list[m.PurchaseOrder]:
    q = select(m.PurchaseOrder)
    if node_id:
        q = q.where(m.PurchaseOrder.node_id == node_id)
    if sku_id:
        q = q.where(m.PurchaseOrder.sku_id == sku_id)
    if only_open:
        q = q.where(m.PurchaseOrder.status.in_(OPEN))
    if run_id:
        q = q.where(m.PurchaseOrder.run_id == run_id)
    return session.exec(q.order_by(m.PurchaseOrder.expected_delivery)).all()


def po_events(session: Session, po_id: str) -> list[m.POEvent]:
    return session.exec(select(m.POEvent).where(m.POEvent.po_id == po_id).order_by(m.POEvent.at)).all()


def transfers(session: Session, sku_id: str | None = None, run_id: str | None = None) -> list[m.Transfer]:
    q = select(m.Transfer)
    if sku_id:
        q = q.where(m.Transfer.sku_id == sku_id)
    if run_id:
        q = q.where(m.Transfer.run_id == run_id)
    return session.exec(q).all()
