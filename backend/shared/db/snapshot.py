"""Planning snapshot: turn DB rows into the engine's OptionContext for one SKU at one node.

Lives in shared because BOTH sides need the identical view:
- read_api shows projections/options to the agent and the UI;
- write_api re-validates a plan against the DB inside its own transaction right before writing
  (asking read_api over HTTP would open a check-then-write race).
It only SELECTs and works with either session type.
"""

from datetime import date, timedelta
from typing import Optional

from sqlmodel import Session, select

from shared.db import models as m
from shared.domain.errors import NotFoundError
from shared.domain.planning import Receipt, SupplierOffer
from shared.engine.options import OptionContext

SIM_DAYS = 30
OPEN_PO_STATUSES = ("sent", "confirmed", "partially_confirmed")


def world(session: Session) -> m.World:
    w = session.get(m.World, 1)
    if w is None:
        raise NotFoundError("world", "no scenario loaded — load a fixture first")
    return w


def offers_for(session: Session, sku_id: str) -> list[SupplierOffer]:
    out = []
    for t in session.exec(select(m.SupplierTerm).where(m.SupplierTerm.sku_id == sku_id)).all():
        s = session.get(m.Supplier, t.supplier_id)
        out.append(SupplierOffer(
            supplier_id=s.id, supplier_name=s.name, active=s.active, unit_cost=t.unit_cost, moq=t.moq,
            case_pack=t.case_pack, lead_time_days=t.lead_time_days, express_lead_days=t.express_lead_days,
            express_premium_per_unit=t.express_premium_per_unit, max_qty=t.max_qty,
            remaining_shelf_life_days=t.remaining_shelf_life_days, delivery_weekdays=s.delivery_weekdays,
            cutoff_hour=s.cutoff_hour, fill_rate=s.fill_rate, on_time_rate=s.on_time_rate,
            lead_time_sigma_days=s.lead_time_sigma_days,
        ))
    return out


def open_receipts(session: Session, node_id: str, sku_id: str, today: date) -> list[Receipt]:
    receipts = []
    pos = session.exec(select(m.PurchaseOrder).where(
        m.PurchaseOrder.node_id == node_id, m.PurchaseOrder.sku_id == sku_id,
        m.PurchaseOrder.status.in_(OPEN_PO_STATUSES), m.PurchaseOrder.expected_delivery >= today,
    )).all()
    for po in pos:
        qty = po.qty_confirmed if po.qty_confirmed is not None else po.qty_ordered
        if qty > 0:
            receipts.append(Receipt(day=(po.expected_delivery - today).days, qty=qty,
                                    remaining_shelf_life_days=po.remaining_shelf_life_days, source=po.id))
    transfers = session.exec(select(m.Transfer).where(
        m.Transfer.to_node == node_id, m.Transfer.sku_id == sku_id,
        m.Transfer.status.in_(("planned", "in_transit")), m.Transfer.eta >= today,
    )).all()
    receipts += [Receipt(day=(t.eta - today).days, qty=t.qty, source=t.id) for t in transfers]
    return sorted(receipts, key=lambda r: r.day)


def budget_remaining(session: Session, node_id: str, category: str, today: date) -> Optional[float]:
    b = session.exec(select(m.Budget).where(
        m.Budget.node_id == node_id, m.Budget.category == category,
        m.Budget.period_start <= today, m.Budget.period_end >= today,
    )).first()
    return None if b is None else round(b.total - b.committed, 2)


def zone_free(session: Session, node_id: str, zone: str, today: date, days: int = SIM_DAYS) -> list[float]:
    z = session.exec(select(m.StorageZone).where(m.StorageZone.node_id == node_id, m.StorageZone.zone == zone)).first()
    if z is None:
        raise NotFoundError("storage_zone", f"{node_id}/{zone}")
    used = {o.day: o.used_l for o in session.exec(select(m.ZoneOccupancy).where(
        m.ZoneOccupancy.node_id == node_id, m.ZoneOccupancy.zone == zone,
        m.ZoneOccupancy.day >= today, m.ZoneOccupancy.day < today + timedelta(days=days),
    )).all()}
    return [round(z.capacity_l - used.get(today + timedelta(days=i), 0.0), 2) for i in range(days)]


def build_context(session: Session, node_id: str, sku_id: str, recommendation_id: Optional[str] = None,
                  exclude_po_ids: tuple[str, ...] = ()) -> OptionContext:
    w = world(session)
    today = w.today
    sku = session.get(m.Sku, sku_id)
    if sku is None:
        raise NotFoundError("sku", sku_id)
    inv = session.exec(select(m.Inventory).where(m.Inventory.node_id == node_id, m.Inventory.sku_id == sku_id)).first()
    if inv is None:
        raise NotFoundError("inventory", f"{node_id}/{sku_id}")
    fc = {f.day: f for f in session.exec(select(m.Forecast).where(
        m.Forecast.node_id == node_id, m.Forecast.sku_id == sku_id, m.Forecast.day >= today,
        m.Forecast.day < today + timedelta(days=SIM_DAYS),
    )).all()}
    last = None
    demand, sigmas = [], []
    for i in range(SIM_DAYS):
        f = fc.get(today + timedelta(days=i)) or last
        if f is None:
            raise NotFoundError("forecast", f"{node_id}/{sku_id}")
        demand.append(f.units)
        sigmas.append(f.sigma)
        last = f
    rec = session.get(m.Recommendation, recommendation_id) if recommendation_id else None
    receipts = [r for r in open_receipts(session, node_id, sku_id, today) if r.source not in exclude_po_ids]
    return OptionContext(
        today=today, now_hour=w.now_hour, on_hand=inv.on_hand,
        on_hand_remaining_shelf_life_days=inv.remaining_shelf_life_days,
        demand=demand, sigmas=sigmas, open_receipts=receipts, unit_volume_l=sku.unit_volume_l,
        zone_free_l=zone_free(session, node_id, sku.zone, today), review_period_days=sku.review_period_days,
        unit_margin=sku.unit_margin, budget_remaining=budget_remaining(session, node_id, sku.category, today),
        offers=offers_for(session, sku_id),
        recommendation_qty=rec.qty if rec else None, recommendation_supplier=rec.supplier_id if rec else None,
    )
