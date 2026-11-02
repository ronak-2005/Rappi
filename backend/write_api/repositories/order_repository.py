"""INSERT/UPDATE for purchase orders, their events and budget commitments."""

from datetime import UTC, date, datetime

from sqlmodel import Session, select

from shared.db import models as m


def now() -> datetime:
    return datetime.now(UTC)


def by_idempotency_key(session: Session, key: str) -> m.PurchaseOrder | None:
    return session.exec(select(m.PurchaseOrder).where(m.PurchaseOrder.idempotency_key == key)).first()


def next_po_id(session: Session) -> str:
    n = len(session.exec(select(m.PurchaseOrder.id).where(m.PurchaseOrder.created_by == "agent")).all())
    return f"PO-A{n + 1:03d}"


def find_identical_open(
    session: Session, node: str, sku: str, supplier: str, qty: int, delivery: date
) -> m.PurchaseOrder | None:
    q = select(m.PurchaseOrder).where(
        m.PurchaseOrder.node_id == node,
        m.PurchaseOrder.sku_id == sku,
        m.PurchaseOrder.supplier_id == supplier,
        m.PurchaseOrder.qty_ordered == qty,
        m.PurchaseOrder.expected_delivery == delivery,
        m.PurchaseOrder.status.in_(("draft", "sent", "confirmed", "partially_confirmed")),
    )
    return session.exec(q).first()


def create_po(session: Session, **fields) -> m.PurchaseOrder:
    po = m.PurchaseOrder(**fields)
    session.add(po)
    session.commit()
    session.refresh(po)
    return po


def update_po(session: Session, po: m.PurchaseOrder, **fields) -> m.PurchaseOrder:
    for k, v in fields.items():
        setattr(po, k, v)
    session.add(po)
    session.commit()
    session.refresh(po)
    return po


def add_event(session: Session, po_id: str, type_: str, payload: dict) -> None:
    session.add(m.POEvent(po_id=po_id, at=now(), type=type_, payload=payload))
    session.commit()


def commit_budget(session: Session, node: str, category: str, today: date, amount: float) -> None:
    b = session.exec(
        select(m.Budget).where(
            m.Budget.node_id == node,
            m.Budget.category == category,
            m.Budget.period_start <= today,
            m.Budget.period_end >= today,
        )
    ).first()
    if b is not None:
        b.committed = round(b.committed + amount, 2)
        session.add(b)
        session.commit()


def set_recommendation_status(session: Session, rec_id: str, status: str) -> None:
    rec = session.get(m.Recommendation, rec_id)
    if rec is not None:
        rec.status = status
        session.add(rec)
        session.commit()


def transfer(session: Session, transfer_id: str) -> m.Transfer | None:
    return session.get(m.Transfer, transfer_id)


def create_transfer(
    session: Session, *, transfer_id: str, from_node: str, to_node: str, sku: str, qty: int, eta: date, run_id: str
) -> m.Transfer:
    """Book a transfer and take the stock out of the source store (it is picked now)."""
    t = m.Transfer(
        id=transfer_id,
        from_node=from_node,
        to_node=to_node,
        sku_id=sku,
        qty=qty,
        eta=eta,
        status="in_transit",
        run_id=run_id,
    )
    inv = session.exec(select(m.Inventory).where(m.Inventory.node_id == from_node, m.Inventory.sku_id == sku)).first()
    inv.on_hand -= qty
    session.add(t)
    session.add(inv)
    session.commit()
    return t
