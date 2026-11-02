"""Option generator + plan evaluator.

`evaluate_plan` is the single source of truth for "what happens if we do X": it projects stock,
prices the plan and runs every rule check. It is used for engine-generated options, for plans the
LLM proposes (validate_plan / validator) and for verification after the supplier answers.

`generate_options` builds the sensible candidates a buyer would consider:
  do_nothing · as_recommended · standard (per supplier) · express · bridge (express + standard)
  · two_drops (storage) · within_budget · waste_free (shelf life)
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel

from shared.config.policy import Policy
from shared.domain.planning import Option, Plan, PlanLine, Receipt, Requirement, SupplierOffer
from shared.engine.calendar import arrival_day, is_delivery_day
from shared.engine.cost import decision_cost
from shared.engine.projection import project
from shared.engine.requirement import net_requirement, round_down_to_pack, round_to_pack


class OptionContext(BaseModel):
    """Everything the engine needs about one SKU at one node. Built by services from the DB."""
    today: date
    now_hour: int
    on_hand: float
    on_hand_remaining_shelf_life_days: Optional[int] = None
    demand: list[float]  # forecast from day 0; its length is the simulation length
    sigmas: list[float]
    open_receipts: list[Receipt]
    unit_volume_l: float
    zone_free_l: list[float]  # free litres for this SKU per day (capacity − other SKUs)
    review_period_days: int
    unit_margin: float
    budget_remaining: Optional[float] = None
    offers: list[SupplierOffer]
    recommendation_qty: Optional[int] = None
    recommendation_supplier: Optional[str] = None


# ---------------------------------------------------------------- helpers
def _offer(ctx: OptionContext, supplier_id: str) -> Optional[SupplierOffer]:
    return next((o for o in ctx.offers if o.supplier_id == supplier_id), None)


def earliest_arrival(ctx: OptionContext, offer: SupplierOffer, mode: str = "standard") -> Optional[int]:
    lead = offer.lead_time_days if mode == "standard" else offer.express_lead_days
    if lead is None:
        return None
    return arrival_day(ctx.today, ctx.now_hour, lead, offer.cutoff_hour, offer.delivery_weekdays)


def reference_offer(ctx: OptionContext) -> SupplierOffer:
    """The supplier that defines the planning horizon: the recommended one, else the cheapest active one."""
    rec = _offer(ctx, ctx.recommendation_supplier) if ctx.recommendation_supplier else None
    if rec and rec.active:
        return rec
    active = [o for o in ctx.offers if o.active] or ctx.offers
    return min(active, key=lambda o: o.unit_cost)


def horizon(ctx: OptionContext) -> int:
    ref = reference_offer(ctx)
    return earliest_arrival(ctx, ref) + ctx.review_period_days


def requirement(ctx: OptionContext, policy: Policy, offer: Optional[SupplierOffer] = None) -> Requirement:
    """Net requirement over the common horizon, rounded to `offer`'s pack/MOQ (reference offer by default)."""
    ref = reference_offer(ctx)
    offer = offer or ref
    arrival = earliest_arrival(ctx, ref)
    return net_requirement(
        on_hand=ctx.on_hand, demand=ctx.demand, sigmas=ctx.sigmas, open_receipts=ctx.open_receipts,
        arrival_day=arrival, review_period_days=ctx.review_period_days, z=policy.planning.service_level_z,
        lead_time_sigma_days=ref.lead_time_sigma_days, moq=offer.moq, case_pack=offer.case_pack,
    )


def _project(ctx: OptionContext, policy: Policy, new: list[Receipt], extra_existing: list[Receipt] | None = None,
             check_from: int = 0):
    req = requirement(ctx, policy)
    return project(
        on_hand=ctx.on_hand, on_hand_remaining_shelf_life_days=ctx.on_hand_remaining_shelf_life_days,
        demand=ctx.demand, receipts=ctx.open_receipts + (extra_existing or []) + new,
        unit_volume_l=ctx.unit_volume_l, zone_free_l=ctx.zone_free_l, safety_stock=req.safety_stock,
        horizon_days=req.horizon_days, sell_buffer_days=policy.planning.shelf_life_sell_buffer_days,
        check_ss_from_day=check_from,
    )


def unavoidable_lost(ctx: OptionContext, policy: Policy) -> float:
    """Lost sales before ANY supplier could deliver (nothing a plan can fix)."""
    arrivals = [a for o in ctx.offers if o.active for m in ("standard", "express")
                if (a := earliest_arrival(ctx, o, m)) is not None]
    first = min(arrivals) if arrivals else 0
    base = _project(ctx, policy, [])
    return sum(d.lost for d in base.days if d.day < first)


# ---------------------------------------------------------------- evaluation
def evaluate_plan(ctx: OptionContext, policy: Policy, plan: Plan, *, option_id: str = "custom",
                  kind: str = "custom", label: str = "Custom plan") -> Option:
    checks: dict[str, bool] = {
        "supplier_known": True, "supplier_active": True, "express_available": True, "qty_positive": True,
        "moq": True, "case_pack": True, "max_qty": True, "delivery_calendar": True,
    }
    notes: list[str] = []
    receipts: list[Receipt] = []
    line_costs: list[tuple[int, float]] = []
    premium = 0.0
    for i, line in enumerate(plan.lines, start=1):
        offer = _offer(ctx, line.supplier_id)
        if offer is None:
            checks["supplier_known"] = False
            notes.append(f"line {i}: unknown supplier {line.supplier_id} for this SKU")
            continue
        if not offer.active:
            checks["supplier_active"] = False
        if line.qty <= 0:
            checks["qty_positive"] = False
        if line.qty < offer.moq:
            checks["moq"] = False
            notes.append(f"line {i}: {line.qty} < MOQ {offer.moq}")
        if offer.case_pack > 1 and line.qty % offer.case_pack:
            checks["case_pack"] = False
            notes.append(f"line {i}: {line.qty} is not a multiple of case pack {offer.case_pack}")
        if line.qty > offer.max_qty:
            checks["max_qty"] = False
        earliest = earliest_arrival(ctx, offer, line.mode)
        if earliest is None:
            checks["express_available"] = False
            notes.append(f"line {i}: supplier {offer.supplier_id} has no express delivery")
            earliest = earliest_arrival(ctx, offer, "standard")
        day = line.delivery_day if line.delivery_day is not None else earliest
        if day < earliest or not is_delivery_day(ctx.today, day, offer.delivery_weekdays):
            checks["delivery_calendar"] = False
            notes.append(f"line {i}: delivery day {day} not possible (earliest {earliest}, weekdays {offer.delivery_weekdays})")
        receipts.append(Receipt(day=day, qty=line.qty, remaining_shelf_life_days=offer.remaining_shelf_life_days,
                                source=f"plan:line{i}", is_new=True))
        line_costs.append((line.qty, offer.unit_cost))
        if line.mode == "express":
            premium += line.qty * offer.express_premium_per_unit

    check_from = min((r.day for r in receipts), default=earliest_arrival(ctx, reference_offer(ctx)))
    proj = _project(ctx, policy, receipts, check_from=check_from)
    base = _project(ctx, policy, [], check_from=check_from)
    total_qty = plan.total_qty
    purchase = round(sum(q * c for q, c in line_costs) + premium, 2)
    waste_pct = round(100 * proj.expired_units_new / total_qty, 1) if total_qty else 0.0
    new_over = [d for d in proj.over_capacity_days if d < proj.horizon_days and d not in base.over_capacity_days]
    avoidable = max(0.0, proj.lost_units - unavoidable_lost(ctx, policy))

    checks["capacity"] = not new_over
    checks["shelf_life"] = waste_pct <= policy.hard_rules.max_expiry_waste_pct
    hard_ok = all(checks.values())

    soft: list[str] = []
    s = policy.soft_rules
    if ctx.budget_remaining is not None and purchase > ctx.budget_remaining + 1e-6:
        soft.append("budget")
    if avoidable > 1e-6:
        soft.append("stockout")
    if proj.below_ss_days:
        soft.append("below_safety_stock")
    if purchase > s.po_value_over:
        soft.append("po_value")
    if ctx.recommendation_qty and total_qty > ctx.recommendation_qty * (1 + s.increase_over_recommendation_pct / 100):
        soft.append("increase_over_recommendation")
    if premium > s.express_premium_total_over:
        soft.append("express_premium")
    if any((o := _offer(ctx, ln.supplier_id)) and o.fill_rate < s.min_supplier_fill_rate for ln in plan.lines):
        soft.append("supplier_reliability")

    cost, breakdown = decision_cost(
        line_costs=line_costs, express_premium=premium, reference_unit_cost=min(o.unit_cost for o in ctx.offers),
        horizon_closes=[d.close for d in proj.days if d.day < proj.horizon_days],
        holding_pct_per_day=policy.costs.holding_cost_pct_per_day, avoidable_lost_units=avoidable,
        unit_margin=ctx.unit_margin, stockout_multiplier=policy.costs.stockout_cost_multiplier,
        expired_units_new=proj.expired_units_new,
    )
    return Option(
        id=option_id, kind=kind, label=label, plan=plan, total_qty=total_qty, purchase_cost=purchase,
        express_premium=round(premium, 2), decision_cost=cost, cost_breakdown=breakdown,
        lost_units=proj.lost_units, expired_units=proj.expired_units_new, waste_pct=waste_pct,
        min_close=proj.min_close, end_close=proj.end_close, over_capacity_days=new_over,
        below_ss_days=proj.below_ss_days, checks=checks, hard_ok=hard_ok, soft_issues=soft, notes=notes,
    )


# ---------------------------------------------------------------- generation
def generate_options(ctx: OptionContext, policy: Policy) -> list[Option]:
    """Candidate plans, best first: hard-feasible, then fewest soft issues, then lowest decision cost."""
    candidates: list[tuple[str, str, str, Plan]] = [("do_nothing", "do_nothing", "Do nothing", Plan())]
    req = requirement(ctx, policy)
    need = req.net_requirement

    if ctx.recommendation_qty and ctx.recommendation_supplier:
        candidates.append(("as_recommended", "as_recommended",
                           f"As recommended: {ctx.recommendation_qty} from {ctx.recommendation_supplier}",
                           Plan(lines=[PlanLine(supplier_id=ctx.recommendation_supplier, qty=ctx.recommendation_qty)])))

    if need > 0:
        for offer in (o for o in ctx.offers if o.active):
            qty = round_to_pack(need, offer.moq, offer.case_pack)
            sid = offer.supplier_id
            std = Plan(lines=[PlanLine(supplier_id=sid, qty=qty)])
            candidates.append((f"standard:{sid}", "standard", f"{qty} from {sid}, standard delivery", std))

            if offer.express_lead_days is not None:
                candidates.append((f"express:{sid}", "express", f"{qty} from {sid}, all express",
                                   Plan(lines=[PlanLine(supplier_id=sid, qty=qty, mode="express")])))
                bridge = _bridge_plan(ctx, policy, offer, need)
                if bridge:
                    b, s_ = bridge.lines
                    candidates.append((f"bridge:{sid}", "bridge",
                                       f"Bridge {b.qty} express + {s_.qty} standard from {sid}", bridge))

            two = _two_drops_plan(ctx, policy, offer, qty)
            if two:
                a, b = two.lines
                candidates.append((f"two_drops:{sid}", "two_drops",
                                   f"{a.qty} on day {a.delivery_day} + {b.qty} on day {b.delivery_day} from {sid}", two))

            if ctx.budget_remaining is not None and qty * offer.unit_cost > ctx.budget_remaining:
                within = round_down_to_pack(ctx.budget_remaining / offer.unit_cost, offer.case_pack)
                if within >= offer.moq and within > 0:
                    candidates.append((f"within_budget:{sid}", "within_budget",
                                       f"{within} from {sid} (fits remaining budget)",
                                       Plan(lines=[PlanLine(supplier_id=sid, qty=within)])))

            wf = _waste_free_qty(ctx, policy, offer, qty)
            if wf is not None:
                candidates.append((f"waste_free:{sid}", "waste_free", f"{wf} from {sid} (sells before expiry)",
                                   Plan(lines=[PlanLine(supplier_id=sid, qty=wf)])))

    seen: set[tuple] = set()
    options: list[Option] = []
    for oid, kind, label, plan in candidates:
        key = tuple((ln.supplier_id, ln.qty, ln.mode, ln.delivery_day) for ln in plan.lines)
        if key in seen:
            continue
        if kind != "as_recommended":  # the recommendation is always shown, even if identical to an option
            seen.add(key)
        options.append(evaluate_plan(ctx, policy, plan, option_id=oid, kind=kind, label=label))

    options.sort(key=lambda o: (not o.hard_ok, len(o.soft_issues), o.decision_cost))
    return options


def _bridge_plan(ctx: OptionContext, policy: Policy, offer: SupplierOffer, need: float) -> Optional[Plan]:
    """Express bridge sized to keep stock ≥ safety stock until the standard delivery, rest standard."""
    std_day = earliest_arrival(ctx, offer, "standard")
    exp_day = earliest_arrival(ctx, offer, "express")
    if exp_day is None or exp_day >= std_day:
        return None
    req = requirement(ctx, policy)
    base = _project(ctx, policy, [])
    if not any((d.lost > 0 or d.close < req.safety_stock) for d in base.days if exp_day <= d.day < std_day):
        return None  # standard delivery is early enough
    open_at_exp = base.days[exp_day].available
    demand_until_std = sum(ctx.demand[exp_day:std_day])
    bridge = round_to_pack(demand_until_std + req.safety_stock - open_at_exp, offer.moq, offer.case_pack)
    rest = round_to_pack(need - bridge, offer.moq, offer.case_pack)
    if bridge <= 0 or rest <= 0:
        return None
    return Plan(lines=[PlanLine(supplier_id=offer.supplier_id, qty=bridge, mode="express"),
                       PlanLine(supplier_id=offer.supplier_id, qty=rest, mode="standard")])


def _two_drops_plan(ctx: OptionContext, policy: Policy, offer: SupplierOffer, qty: int) -> Optional[Plan]:
    """If one delivery overflows storage: first drop = what fits, second drop on the first day it fits
    without breaching safety stock before it."""
    single = evaluate_plan(ctx, policy, Plan(lines=[PlanLine(supplier_id=offer.supplier_id, qty=qty)]))
    if single.checks["capacity"]:
        return None
    day1 = earliest_arrival(ctx, offer)
    base = _project(ctx, policy, [])
    stock_at_day1 = base.days[day1].available
    fits = (ctx.zone_free_l[day1] / ctx.unit_volume_l) - stock_at_day1
    drop1 = round_down_to_pack(fits, offer.case_pack)
    if drop1 < offer.moq:
        return None
    drop2 = round_to_pack(qty - drop1, offer.moq, offer.case_pack)
    h = horizon(ctx)
    best: Optional[Plan] = None
    for d2 in range(day1 + 1, h):
        if not is_delivery_day(ctx.today, d2, offer.delivery_weekdays):
            continue
        plan = Plan(lines=[PlanLine(supplier_id=offer.supplier_id, qty=drop1, delivery_day=day1),
                           PlanLine(supplier_id=offer.supplier_id, qty=drop2, delivery_day=d2)])
        ev = evaluate_plan(ctx, policy, plan)
        if ev.checks["capacity"] and not ev.below_ss_days:
            return plan
        if ev.checks["capacity"] and best is None:
            best = plan
    return best


def _waste_free_qty(ctx: OptionContext, policy: Policy, offer: SupplierOffer, qty: int) -> Optional[int]:
    """Largest pack-multiple ≥ MOQ below `qty` that meets the shelf-life rule (None if qty already does)."""
    if offer.remaining_shelf_life_days is None:
        return None
    full = evaluate_plan(ctx, policy, Plan(lines=[PlanLine(supplier_id=offer.supplier_id, qty=qty)]))
    if full.checks["shelf_life"]:
        return None
    q = qty - offer.case_pack
    while q >= max(offer.moq, 1):
        ev = evaluate_plan(ctx, policy, Plan(lines=[PlanLine(supplier_id=offer.supplier_id, qty=q)]))
        if ev.checks["shelf_life"]:
            return q
        q -= offer.case_pack
    return None
