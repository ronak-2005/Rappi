"""The rulebook. Re-evaluates a plan against the CURRENT database (inside the write transaction)
and runs every hard and soft rule. Hard failure → plan blocked. Soft violation → human approval."""

from datetime import timedelta
from typing import Optional

from sqlmodel import Session

from shared.config.policy import Policy
from shared.db import snapshot
from shared.domain.decision import ValidationReport
from shared.domain.planning import Plan, PlanLine
from shared.engine.options import earliest_arrival, evaluate_plan
from write_api.repositories import order_repository
from write_api.validation.rules.base import RuleInput
from write_api.validation.rules.hard import capacity, delivery_calendar, duplicate_po, moq_pack, shelf_life, supplier
from write_api.validation.rules.soft import (below_safety_stock, budget, express_premium, increase_over_recommendation,
                                             po_value, stockout, supplier_reliability)

HARD_RULES = [supplier.check, moq_pack.check, delivery_calendar.check, capacity.check, shelf_life.check,
              duplicate_po.check]
SOFT_RULES = [budget.check, stockout.check, below_safety_stock.check, po_value.check,
              increase_over_recommendation.check, express_premium.check, supplier_reliability.check]


def validate(session: Session, policy: Policy, node: str, sku: str, lines: list[PlanLine],
             recommendation_id: Optional[str] = None) -> ValidationReport:
    ctx = snapshot.build_context(session, node, sku, recommendation_id)
    evaluation = evaluate_plan(ctx, policy, Plan(lines=lines))

    duplicates = []
    for ln in lines:
        offer = next((o for o in ctx.offers if o.supplier_id == ln.supplier_id), None)
        if offer is None:
            continue
        day = ln.delivery_day if ln.delivery_day is not None else earliest_arrival(ctx, offer, ln.mode)
        if day is None:
            continue
        po = order_repository.find_identical_open(session, node, sku, ln.supplier_id, ln.qty,
                                                  ctx.today + timedelta(days=day))
        if po:
            duplicates.append(po.id)

    inp = RuleInput(evaluation=evaluation, ctx=ctx, lines=lines, policy=policy, duplicate_po_ids=duplicates)
    results = [rule(inp) for rule in HARD_RULES] + ([rule(inp) for rule in SOFT_RULES] if lines else [])
    if not lines:  # "do nothing" (reject/investigate): only the consequences matter
        results += [stockout.check(inp), below_safety_stock.check(inp)]
    hard = [r for r in results if r.kind == "hard" and not r.passed]
    soft = [r for r in results if r.kind == "soft" and not r.passed]
    return ValidationReport(passed=not hard, requires_approval=bool(soft), hard_failures=hard, soft_violations=soft,
                            all_results=results, evaluation=evaluation)
