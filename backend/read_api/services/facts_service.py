"""Read-side query logic for facts. Returns compact, explicit dicts: they are read by the LLM agent
(token cost matters) and by the UI. Every response says which date 'today' is."""

from datetime import timedelta

from sqlmodel import Session

from read_api.repositories import catalog_repository as catalog
from read_api.repositories import order_repository as orders
from read_api.repositories import stock_repository as stock
from shared.db import snapshot
from shared.domain.errors import NotFoundError
from shared.engine.calendar import arrival_day


def _today(session: Session):
    return snapshot.world(session).today


def world(session: Session) -> dict:
    w = snapshot.world(session)
    return {
        "fixture_id": w.fixture_id,
        "today": w.today.isoformat(),
        "weekday": w.today.strftime("%A"),
        "now_hour": w.now_hour,
    }


def situation(session: Session, recommendation_id: str) -> dict:
    rec = catalog.recommendation(session, recommendation_id)
    if rec is None:
        raise NotFoundError("recommendation", recommendation_id)
    return {
        "type": "recommendation_review",
        "today": _today(session).isoformat(),
        "recommendation": {
            "id": rec.id,
            "node": rec.node_id,
            "sku": rec.sku_id,
            "qty": rec.qty,
            "supplier": rec.supplier_id,
            "source": rec.source,
            "status": rec.status,
        },
        "question": "Should this recommendation be accepted, modified, rejected or investigated further?",
    }


def supplier_event_situation(session: Session, event_id: str) -> dict:
    from shared.db import models as m

    ev = session.get(m.SupplierEvent, event_id)
    if ev is None:
        raise NotFoundError("supplier_event", event_id)
    po = session.get(m.PurchaseOrder, ev.po_id)
    return {
        "type": "supplier_shortfall",
        "today": _today(session).isoformat(),
        "event": {
            "id": ev.id,
            "supplier": ev.supplier_id,
            "node": ev.node_id,
            "sku": ev.sku_id,
            "message": ev.message,
            "received_on": ev.received_on.isoformat(),
        },
        "purchase_order": {
            "id": po.id,
            "qty_ordered": po.qty_ordered,
            "qty_confirmed": po.qty_confirmed,
            "status": po.status,
            "expected_delivery": po.expected_delivery.isoformat(),
        },
        "question": "The supplier cannot deliver the full order. What, if anything, should happen next?",
    }


def demand_alert_situation(session: Session, alert_id: str) -> dict:
    from shared.db import models as m

    al = session.get(m.DemandAlert, alert_id)
    if al is None:
        raise NotFoundError("demand_alert", alert_id)
    return {
        "type": "demand_change",
        "today": _today(session).isoformat(),
        "alert": {
            "id": al.id,
            "node": al.node_id,
            "sku": al.sku_id,
            "message": al.message,
            "raised_on": al.raised_on.isoformat(),
        },
        "question": "Sales diverge from the forecast. Does the purchasing plan need to change?",
    }


def sku_profile(session: Session, sku_id: str) -> dict:
    s = catalog.sku(session, sku_id)
    if s is None:
        raise NotFoundError("sku", sku_id)
    return s.model_dump()


def inventory(session: Session, node_id: str, sku_id: str) -> dict:
    today = _today(session)
    inv = stock.inventory(session, node_id, sku_id)
    if inv is None:
        raise NotFoundError("inventory", f"{node_id}/{sku_id}")
    return {
        "node": node_id,
        "sku": sku_id,
        "on_hand": inv.on_hand,
        "last_counted_at": inv.last_counted_at.isoformat(),
        "last_counted_days_ago": (today - inv.last_counted_at).days,
        "remaining_shelf_life_days": inv.remaining_shelf_life_days,
        "today": today.isoformat(),
    }


def open_purchase_orders(session: Session, node_id: str, sku_id: str) -> dict:
    today = _today(session)
    pos = orders.purchase_orders(session, node_id, sku_id, only_open=True)
    return {
        "node": node_id,
        "sku": sku_id,
        "today": today.isoformat(),
        "open_purchase_orders": [
            {
                "id": p.id,
                "supplier": p.supplier_id,
                "qty_ordered": p.qty_ordered,
                "qty_confirmed": p.qty_confirmed,
                "status": p.status,
                "mode": p.mode,
                "expected_delivery": p.expected_delivery.isoformat(),
                "arrives_in_days": (p.expected_delivery - today).days,
                "created_by": p.created_by,
            }
            for p in pos
        ],
    }


def sales_history(session: Session, node_id: str, sku_id: str, days: int = 14) -> dict:
    today = _today(session)
    rows = stock.sales(session, node_id, sku_id, today, days)
    clean = [r.units for r in rows if not r.stocked_out]
    last7 = [r.units for r in rows[-7:] if not r.stocked_out]
    return {
        "node": node_id,
        "sku": sku_id,
        "today": today.isoformat(),
        "daily": [{"date": r.day.isoformat(), "units": r.units, "stocked_out": r.stocked_out} for r in rows],
        "avg_per_day": round(sum(clean) / len(clean), 1) if clean else None,
        "avg_last_7_days": round(sum(last7) / len(last7), 1) if last7 else None,
        "stockout_days": sum(r.stocked_out for r in rows),
    }


def forecast(session: Session, node_id: str, sku_id: str, days: int = 14) -> dict:
    today = _today(session)
    rows = stock.forecast(session, node_id, sku_id, today, days)
    return {
        "node": node_id,
        "sku": sku_id,
        "today": today.isoformat(),
        "daily": [{"date": f.day.isoformat(), "units": f.units, "sigma": f.sigma} for f in rows],
        "avg_per_day": round(sum(f.units for f in rows) / len(rows), 1) if rows else None,
    }


def promotions(session: Session, node_id: str, sku_id: str) -> dict:
    today = _today(session)
    return {
        "node": node_id,
        "sku": sku_id,
        "today": today.isoformat(),
        "promotions": [
            {
                "start": p.start.isoformat(),
                "end": p.end.isoformat(),
                "uplift_pct": p.uplift_pct,
                "description": p.description,
                "active_today": p.start <= today <= p.end,
            }
            for p in stock.promotions(session, node_id, sku_id, today)
        ],
    }


def supplier_terms(session: Session, sku_id: str, node_id: str | None = None) -> dict:
    w = snapshot.world(session)
    out = []
    for o in snapshot.offers_for(session, sku_id):
        std = arrival_day(w.today, w.now_hour, o.lead_time_days, o.cutoff_hour, o.delivery_weekdays)
        exp = (
            arrival_day(w.today, w.now_hour, o.express_lead_days, o.cutoff_hour, o.delivery_weekdays)
            if o.express_lead_days is not None
            else None
        )
        d = o.model_dump()
        d["earliest_standard_arrival"] = (w.today + timedelta(days=std)).isoformat()
        d["earliest_standard_arrival_in_days"] = std
        d["earliest_express_arrival_in_days"] = exp
        out.append(d)
    return {"sku": sku_id, "today": w.today.isoformat(), "now_hour": w.now_hour, "suppliers": out}


def supplier_performance(session: Session, supplier_id: str) -> dict:
    s = catalog.supplier(session, supplier_id)
    if s is None:
        raise NotFoundError("supplier", supplier_id)
    return {
        "supplier": s.id,
        "name": s.name,
        "active": s.active,
        "fill_rate": s.fill_rate,
        "on_time_rate": s.on_time_rate,
        "lead_time_sigma_days": s.lead_time_sigma_days,
        "orders_observed": s.orders_observed,
    }


def budget(session: Session, node_id: str, category: str) -> dict:
    today = _today(session)
    b = stock.budget(session, node_id, category, today)
    if b is None:
        return {"node": node_id, "category": category, "budget": None, "note": "no budget limit configured"}
    return {
        "node": node_id,
        "category": category,
        "period_start": b.period_start.isoformat(),
        "period_end": b.period_end.isoformat(),
        "total": b.total,
        "committed": b.committed,
        "remaining": round(b.total - b.committed, 2),
    }


def storage_status(session: Session, node_id: str, zone: str, days: int = 10) -> dict:
    today = _today(session)
    z = stock.storage_zone(session, node_id, zone)
    if z is None:
        raise NotFoundError("storage_zone", f"{node_id}/{zone}")
    free = snapshot.zone_free(session, node_id, zone, today, days)
    return {
        "node": node_id,
        "zone": zone,
        "capacity_l": z.capacity_l,
        "today": today.isoformat(),
        "free_for_this_sku_l_by_day": [
            {"date": (today + timedelta(days=i)).isoformat(), "free_l": f} for i, f in enumerate(free)
        ],
        "note": "free = capacity minus litres used by other SKUs; this SKU's own stock is NOT subtracted",
    }


def other_nodes_stock(session: Session, sku_id: str, exclude_node: str) -> dict:
    from shared.config.policy import get_policy

    surplus = {t.node_id: t for t in snapshot.transfer_sources(session, exclude_node, sku_id, get_policy())}
    return {
        "sku": sku_id,
        "to_node": exclude_node,
        "note": "can_spare = stock beyond that store's own need (demand + safety stock over its protection interval)",
        "nodes": [
            {
                "node": i.node_id,
                "on_hand": i.on_hand,
                "can_spare": surplus[i.node_id].surplus if i.node_id in surplus else 0,
                "transfer_lead_days": surplus[i.node_id].lead_days if i.node_id in surplus else None,
                "transfer_cost_per_unit": surplus[i.node_id].cost_per_unit if i.node_id in surplus else None,
            }
            for i in stock.inventory_other_nodes(session, sku_id, exclude_node)
        ],
    }
