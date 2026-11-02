"""Build engine inputs straight from a fixture file (no DB), so engine tests stay pure."""

from shared.domain.fixtures import FixtureSpec, load_fixture_file
from shared.domain.planning import Receipt, SupplierOffer
from shared.engine.options import OptionContext


def ctx_from_fixture(fixture_id: str, node: str | None = None, sku: str | None = None) -> OptionContext:
    fx: FixtureSpec = load_fixture_file(fixture_id)
    w = fx.world
    rec = fx.trigger.recommendation
    node = node or (rec.node if rec else w.nodes[0].id)
    sku_id = sku or (rec.sku if rec else w.skus[0].id)
    sku = next(s for s in w.skus if s.id == sku_id)
    inv = next(i for i in w.inventory if i.node == node and i.sku == sku_id)
    fc = next(f for f in w.forecasts if f.node == node and f.sku == sku_id)
    demand = fc.daily if fc.daily is not None else [fc.units_per_day] * fc.days
    zone = next(z for z in w.storage_zones if z.node == node and z.zone == sku.zone)
    budget = next((b for b in w.budgets if b.node == node and b.category == sku.category), None)
    suppliers = {s.id: s for s in w.suppliers}
    offers = []
    for t in w.supplier_terms:
        if t.sku != sku_id:
            continue
        s = suppliers[t.supplier]
        offers.append(
            SupplierOffer(
                supplier_id=s.id,
                supplier_name=s.name,
                active=s.active,
                unit_cost=t.unit_cost,
                moq=t.moq,
                case_pack=t.case_pack,
                lead_time_days=t.lead_time_days,
                express_lead_days=t.express_lead_days,
                express_premium_per_unit=t.express_premium_per_unit,
                max_qty=t.max_qty,
                remaining_shelf_life_days=t.remaining_shelf_life_days,
                delivery_weekdays=s.delivery_weekdays,
                cutoff_hour=s.cutoff_hour,
                fill_rate=s.fill_rate,
                on_time_rate=s.on_time_rate,
                lead_time_sigma_days=s.lead_time_sigma_days,
            )
        )
    receipts = [
        Receipt(
            day=p.arrives_in_days,
            qty=p.qty_confirmed or p.qty,
            remaining_shelf_life_days=p.remaining_shelf_life_days,
            source=p.id,
        )
        for p in w.open_pos
        if p.node == node and p.sku == sku_id
    ]
    return OptionContext(
        today=fx.today,
        now_hour=fx.now_hour,
        on_hand=inv.on_hand,
        on_hand_remaining_shelf_life_days=inv.remaining_shelf_life_days,
        demand=list(demand),
        sigmas=[fc.sigma] * len(demand),
        open_receipts=receipts,
        unit_volume_l=sku.unit_volume_l,
        zone_free_l=[zone.capacity_l - zone.other_skus_used_l] * len(demand),
        review_period_days=sku.review_period_days,
        unit_margin=sku.unit_margin,
        budget_remaining=(budget.total - budget.committed) if budget else None,
        offers=offers,
        recommendation_qty=rec.qty if rec else None,
        recommendation_supplier=rec.supplier if rec else None,
    )
