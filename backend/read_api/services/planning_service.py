"""Read-side planning queries: requirement, projection, options, plan evaluation, data quality.
Combines the planning snapshot (DB → engine input) with the pure engine. Changes nothing."""

from datetime import timedelta
from typing import Optional

from sqlmodel import Session

from read_api.repositories import stock_repository as stock
from shared.config.policy import Policy
from shared.db import snapshot
from shared.domain.planning import DemandAssumption, Plan
from shared.engine import data_quality
from shared.engine.options import OptionContext, evaluate_plan, evaluate_with_projection, generate_options, requirement


def _day(ctx: OptionContext, d: int) -> str:
    return (ctx.today + timedelta(days=d)).isoformat()


def get_requirement(session: Session, policy: Policy, node: str, sku: str, rec_id: Optional[str] = None,
                    demand: Optional[DemandAssumption] = None) -> dict:
    ctx = snapshot.build_context(session, node, sku, rec_id, demand_assumption=demand)
    r = requirement(ctx, policy)
    out = r.model_dump()
    out["today"] = ctx.today.isoformat()
    out["arrival_date"] = _day(ctx, r.arrival_day)
    out["formula"] = (f"need = demand over {r.horizon_days} days ({r.demand_over_horizon:g}) + safety stock "
                      f"({r.safety_stock:g}) − on hand ({r.on_hand:g}) − open POs arriving in time "
                      f"({r.open_receipts_in_horizon:g}) = {r.net_requirement:g} units needed; rounded to "
                      f"{r.rounded_for_supplier}'s MOQ {r.moq} / case pack {r.case_pack} → {r.order_qty} "
                      f"(other suppliers round differently: see generate_options)")
    out["open_receipts"] = [x.model_dump() for x in ctx.open_receipts]
    out["demand_basis"] = ctx.demand_note
    return out


def _projection_rows(ctx: OptionContext, proj, days: Optional[int]) -> list[dict]:
    limit = days or proj.horizon_days
    return [{"date": _day(ctx, d.day), **d.model_dump()} for d in proj.days[:limit]]


def get_projection(session: Session, policy: Policy, node: str, sku: str, plan: Optional[Plan] = None,
                   rec_id: Optional[str] = None, days: Optional[int] = None,
                   demand: Optional[DemandAssumption] = None) -> dict:
    """Day-by-day stock if we do nothing (plan=None) or if we execute `plan`."""
    ctx = snapshot.build_context(session, node, sku, rec_id, demand_assumption=demand)
    ev, proj = evaluate_with_projection(ctx, policy, plan or Plan())
    return {"today": ctx.today.isoformat(), "safety_stock": proj.safety_stock, "horizon_days": proj.horizon_days,
            "demand_basis": ctx.demand_note, "summary": {k: v for k, v in ev.model_dump().items()
                        if k in ("lost_units", "expired_units", "min_close", "end_close", "over_capacity_days",
                                 "below_ss_days", "hard_ok", "soft_issues", "checks")},
            "days": _projection_rows(ctx, proj, days)}


def get_options(session: Session, policy: Policy, node: str, sku: str, rec_id: Optional[str] = None,
                demand: Optional[DemandAssumption] = None) -> dict:
    ctx = snapshot.build_context(session, node, sku, rec_id, demand_assumption=demand)
    opts = generate_options(ctx, policy)
    for o in opts:
        for ln in o.plan.lines:
            if ln.delivery_day is not None:
                ln_date = _day(ctx, ln.delivery_day)
                o.notes.append(f"{ln.supplier_id} {ln.qty} delivered {ln_date}")
    return {"today": ctx.today.isoformat(), "demand_basis": ctx.demand_note,
            "ranking": "hard-feasible first, then fewest soft issues (each needs human approval), then lowest decision cost",
            "options": [o.model_dump() for o in opts]}


def evaluate(session: Session, policy: Policy, node: str, sku: str, plan: Plan, rec_id: Optional[str] = None,
             demand: Optional[DemandAssumption] = None) -> dict:
    ctx = snapshot.build_context(session, node, sku, rec_id, demand_assumption=demand)
    return evaluate_plan(ctx, policy, plan).model_dump()


def get_data_quality(session: Session, policy: Policy, node: str, sku: str) -> dict:
    today = snapshot.world(session).today
    inv = stock.inventory(session, node, sku)
    sales = stock.sales(session, node, sku, today, 14)
    fc = stock.forecast(session, node, sku, today, 7)
    days_ago = (today - inv.last_counted_at).days
    anomalies = data_quality.check(
        on_hand=inv.on_hand, last_counted_days_ago=days_ago,
        sales=[((today - s.day).days, s.units, s.stocked_out) for s in sales],
        receipts_last_days=stock.received_since(session, node, sku, inv.last_counted_at, today),
        forecast_next_7_avg=(sum(f.units for f in fc) / len(fc)) if fc else 0,
        stale_count_days=policy.data_quality.stale_count_days,
        forecast_vs_sales_ratio_max=policy.data_quality.forecast_vs_sales_ratio_max,
    )
    return {"node": node, "sku": sku, "today": today.isoformat(), "ok": not anomalies,
            "anomalies": [a.model_dump() for a in anomalies]}


def get_demand_signal(session: Session, node: str, sku: str) -> dict:
    return {"node": node, "sku": sku, "today": snapshot.world(session).today.isoformat(),
            **snapshot.demand_signal(session, node, sku).model_dump()}
