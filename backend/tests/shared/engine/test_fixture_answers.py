"""The engine must reproduce every fixture's hand-computed answer.

If one of these fails, either the arithmetic in the fixture notes or the engine is wrong:
both are written independently on purpose.
"""

from shared.config.policy import load_policy
from shared.domain.planning import Plan, PlanLine
from shared.engine.options import evaluate_plan, generate_options, requirement
from tests.shared.engine.helpers import ctx_from_fixture

POLICY = load_policy()


def best(fixture_id):
    return generate_options(ctx_from_fixture(fixture_id), POLICY)[0]


def by_id(fixture_id, option_id):
    return next(o for o in generate_options(ctx_from_fixture(fixture_id), POLICY) if o.id == option_id)


def test_s1_accept():
    ctx = ctx_from_fixture("s1_accept")
    req = requirement(ctx, POLICY)
    assert (req.horizon_days, req.safety_stock, req.net_requirement, req.order_qty) == (10, 157, 757, 760)
    b = best("s1_accept")
    assert b.kind == "as_recommended" and b.total_qty == 760 and b.hard_ok and not b.soft_issues  # → accept
    assert b.end_close == 160


def test_s1_modify_open_po_ignored():
    req = requirement(ctx_from_fixture("s1_modify_open_po_ignored"), POLICY)
    assert req.net_requirement == 457 and req.order_qty == 500
    b = best("s1_modify_open_po_ignored")
    assert b.total_qty == 500 and b.hard_ok and not b.soft_issues
    rec = by_id("s1_modify_open_po_ignored", "as_recommended")
    assert not rec.checks["capacity"]  # 400 + 800 = 1200 L > 900 L on day 3
    assert "budget" in rec.soft_issues  # 960 > 700
    assert b.end_close == 200


def test_s1_reject_overstock():
    req = requirement(ctx_from_fixture("s1_reject_overstock"), POLICY)
    assert req.net_requirement == -293 and req.order_qty == 0
    b = best("s1_reject_overstock")
    assert b.kind == "do_nothing" and b.hard_ok and not b.soft_issues


def test_s1_moq_vs_shelf_life_prefers_low_moq_supplier():
    rec = by_id("s1_modify_moq_vs_shelf_life", "as_recommended")
    assert not rec.checks["shelf_life"] and rec.expired_units == 260
    b = best("s1_modify_moq_vs_shelf_life")
    assert b.plan.lines[0].supplier_id == "SUP_B" and b.total_qty == 320
    assert b.expired_units == 0 and b.hard_ok and not b.soft_issues


def test_s4_storage_two_drops():
    b = best("s4_storage_two_drops")
    assert b.kind == "two_drops" and b.hard_ok and not b.soft_issues
    assert [(ln.qty, ln.delivery_day) for ln in b.plan.lines] == [(700, 2), (460, 6)]
    single = by_id("s4_storage_two_drops", "standard:SUP_A")
    assert not single.checks["capacity"]


def test_s4_budget_needs_approval_either_way():
    opts = generate_options(ctx_from_fixture("s4_budget_partial_needs_approval"), POLICY)
    feasible = [o for o in opts if o.hard_ok and o.kind != "do_nothing"]
    assert feasible and all(o.soft_issues for o in feasible)
    full = next(o for o in opts if o.id == "standard:SUP_A")
    within = next(o for o in opts if o.id == "within_budget:SUP_A")
    assert full.total_qty == 760 and full.soft_issues == ["budget"]
    assert within.total_qty == 500 and {"stockout", "below_safety_stock"} <= set(within.soft_issues)


def test_s4_express_bridge():
    b = best("s4_leadtime_express_bridge")
    assert b.kind == "bridge" and b.hard_ok and not b.soft_issues
    assert [(ln.qty, ln.mode) for ln in b.plan.lines] == [(320, "express"), (700, "standard")]
    assert b.express_premium == 96 and b.end_close == 170
    std = by_id("s4_leadtime_express_bridge", "standard:SUP_A")
    assert std.lost_units == 150 and "stockout" in std.soft_issues
    allx = by_id("s4_leadtime_express_bridge", "express:SUP_A")
    assert "express_premium" in allx.soft_issues


def test_s4_moq_exceeds_shelf_life_has_no_clean_option():
    opts = generate_options(ctx_from_fixture("s4_moq_exceeds_shelf_life"), POLICY)
    buys = [o for o in opts if o.kind != "do_nothing"]
    assert buys and not any(o.hard_ok for o in buys)
    nothing = next(o for o in opts if o.kind == "do_nothing")
    assert "stockout" in nothing.soft_issues


def test_partial_confirmation_replan_numbers():
    """s4_feedback_partial_confirm: after SUP_A confirms 250 of 500, the gap is ~207 → 220 from SUP_B."""
    from shared.domain.planning import Receipt

    ctx = ctx_from_fixture("s4_feedback_partial_confirm")
    first = evaluate_plan(ctx, POLICY, Plan(lines=[PlanLine(supplier_id="SUP_A", qty=500)]))
    assert first.hard_ok and not first.soft_issues
    ctx.open_receipts.append(Receipt(day=3, qty=250, remaining_shelf_life_days=12, source="PO-new"))
    after_partial = evaluate_plan(ctx, POLICY, Plan())
    assert after_partial.lost_units == 50  # → verification UNACCEPTABLE
    ctx.budget_remaining = 700 - 300
    req = requirement(ctx, POLICY)
    assert req.net_requirement == 207
    b = generate_options(ctx, POLICY)[0]
    assert b.plan.lines[0].supplier_id == "SUP_B" and b.total_qty == 220 and b.hard_ok and not b.soft_issues
    assert b.end_close == 170


def test_invalid_custom_plan_is_flagged():
    ctx = ctx_from_fixture("s1_modify_open_po_ignored")
    bad = evaluate_plan(ctx, POLICY, Plan(lines=[PlanLine(supplier_id="SUP_A", qty=450)]))
    assert not bad.checks["moq"] and not bad.checks["case_pack"] and not bad.hard_ok
    unknown = evaluate_plan(ctx, POLICY, Plan(lines=[PlanLine(supplier_id="NOPE", qty=500)]))
    assert not unknown.checks["supplier_known"]
