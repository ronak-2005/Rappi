"""Write-side DB access for (re)building a scenario world from a fixture."""

from datetime import timedelta

from sqlmodel import Session, SQLModel

from shared.db import models as m
from shared.domain.fixtures import FixtureSpec


def reset_database(session: Session) -> None:
    """Delete every row in every table (keeps the schema)."""
    for table in reversed(SQLModel.metadata.sorted_tables):
        session.execute(table.delete())
    session.commit()


def insert_world(session: Session, fx: FixtureSpec) -> None:
    w, today = fx.world, fx.today
    day = lambda offset: today + timedelta(days=offset)  # noqa: E731

    session.add(m.World(fixture_id=fx.id, today=today, now_hour=fx.now_hour))
    session.add_all(m.Node(id=n.id, name=n.name, city=n.city) for n in w.nodes)

    for z in w.storage_zones:
        session.add(m.StorageZone(node_id=z.node, zone=z.zone, capacity_l=z.capacity_l))
        # other SKUs' occupancy from 30 days back to 60 days ahead
        session.add_all(
            m.ZoneOccupancy(node_id=z.node, zone=z.zone, day=day(i), used_l=z.other_skus_used_l)
            for i in range(-30, 60)
        )

    session.add_all(m.Sku(**s.model_dump()) for s in w.skus)

    for inv in w.inventory:
        session.add(m.Inventory(
            node_id=inv.node, sku_id=inv.sku, on_hand=inv.on_hand,
            last_counted_at=day(-inv.last_counted_days_ago),
            remaining_shelf_life_days=inv.remaining_shelf_life_days,
        ))

    for f in w.forecasts:
        values = f.daily if f.daily is not None else [f.units_per_day] * f.days
        session.add_all(
            m.Forecast(node_id=f.node, sku_id=f.sku, day=day(i), units=float(v), sigma=f.sigma)
            for i, v in enumerate(values)
        )

    for s in w.sales_history:
        values = s.daily if s.daily is not None else [s.units_per_day] * s.days
        n = len(values)
        for i, units in enumerate(values):
            days_ago = n - i  # last element = yesterday
            session.add(m.SalesHistory(
                node_id=s.node, sku_id=s.sku, day=day(-days_ago), units=int(units),
                stocked_out=days_ago in s.stocked_out_days_ago,
            ))

    for s in w.suppliers:
        session.add(m.Supplier(**s.model_dump()))

    for t in w.supplier_terms:
        data = t.model_dump(exclude={"supplier", "sku"})
        session.add(m.SupplierTerm(
            supplier_id=t.supplier, sku_id=t.sku,
            express_available=t.express_lead_days is not None, **data,
        ))

    for po in w.open_pos:
        session.add(m.PurchaseOrder(
            id=po.id, node_id=po.node, sku_id=po.sku, supplier_id=po.supplier,
            qty_ordered=po.qty,
            qty_confirmed=po.qty_confirmed if po.qty_confirmed is not None else (po.qty if po.status == "confirmed" else None),
            unit_cost=po.unit_cost, mode=po.mode, status=po.status,
            order_date=day(-po.ordered_days_ago), expected_delivery=day(po.arrives_in_days),
            remaining_shelf_life_days=po.remaining_shelf_life_days, created_by="system",
        ))

    for b in w.budgets:
        session.add(m.Budget(
            node_id=b.node, category=b.category, period_start=today,
            period_end=day(b.period_days), total=b.total, committed=b.committed,
        ))

    for p in w.promotions:
        session.add(m.Promotion(
            node_id=p.node, sku_id=p.sku, start=day(p.starts_in_days), end=day(p.ends_in_days),
            uplift_pct=p.uplift_pct, description=p.description,
        ))

    rec = fx.trigger.recommendation
    if rec:
        session.add(m.Recommendation(
            id=rec.id, node_id=rec.node, sku_id=rec.sku, qty=rec.qty, supplier_id=rec.supplier,
            source=rec.source, created_at=today,
        ))

    session.commit()
