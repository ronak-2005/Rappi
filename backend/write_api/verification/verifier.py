"""Feedback loop #2: after executing, compare what actually happened with what the plan expected.

Re-reads the DB (which now holds the supplier's real answers), re-projects stock, and classifies:
  OK            coverage is as planned
  DEGRADED_OK   something differs (late, partial, price) or a known/approved risk remains, but no new harm
  UNACCEPTABLE  the real outcome creates avoidable lost sales, a storage overflow, or a deep safety-stock breach
The orchestrator re-plans on UNACCEPTABLE (bounded) and escalates when re-planning runs out.
"""

from sqlmodel import Session

from shared.config.policy import Policy
from shared.db import snapshot
from shared.domain.decision import ExecutionResult, VerificationReport
from shared.domain.planning import DemandAssumption, Option, Plan
from shared.engine.options import evaluate_plan, requirement


def verify(
    session: Session,
    policy: Policy,
    *,
    node: str,
    sku: str,
    expected: Option,
    execution: ExecutionResult,
    recommendation_id: str | None = None,
    demand: DemandAssumption | None = None,
) -> VerificationReport:
    # same demand basis the plan was approved on (forecast, or the agent's evidence-backed assumption)
    ctx = snapshot.build_context(session, node, sku, recommendation_id, demand_assumption=demand)
    actual = evaluate_plan(ctx, policy, Plan())  # the executed POs are now open receipts in the DB
    ss = requirement(ctx, policy).safety_stock

    diffs = []
    for ln in execution.lines:
        if ln.status in ("failed", "rejected"):
            diffs.append(f"{ln.po_id} {ln.supplier_id}: {ln.status} ({ln.message or 'no detail'})")
            continue
        if ln.qty_confirmed < ln.qty_requested:
            diffs.append(f"{ln.po_id} {ln.supplier_id}: confirmed {ln.qty_confirmed} of {ln.qty_requested}")
        if ln.confirmed_delivery and ln.confirmed_delivery != ln.requested_delivery:
            diffs.append(f"{ln.po_id}: delivery moved {ln.requested_delivery} → {ln.confirmed_delivery}")
        if ln.replayed or ln.attempts > 1:
            diffs.append(f"{ln.po_id}: needed {ln.attempts} attempt(s) (idempotent retry, no duplicate)")

    exp = {
        "lost_units": expected.lost_units,
        "min_close": expected.min_close,
        "end_close": expected.end_close,
        "below_ss_days": expected.below_ss_days,
    }
    act = {
        "lost_units": actual.lost_units,
        "min_close": actual.min_close,
        "end_close": actual.end_close,
        "below_ss_days": actual.below_ss_days,
        "over_capacity_days": actual.over_capacity_days,
        "soft_issues": actual.soft_issues,
    }
    residual = max(0.0, requirement(ctx, policy).net_requirement)

    no_worse = (
        actual.lost_units <= expected.lost_units + 0.5
        and actual.min_close >= expected.min_close - 0.5
        and not actual.over_capacity_days
    )
    clean = not actual.soft_issues and not actual.over_capacity_days
    material_diffs = [d for d in diffs if "idempotent retry" not in d]

    if no_worse:
        if clean and not material_diffs:
            status, msg = "OK", "Outcome matches the plan; coverage confirmed by re-projection."
        elif clean:
            status, msg = "DEGRADED_OK", "Supplier answer differs from the request, but coverage still holds."
        else:
            status, msg = "DEGRADED_OK", "Outcome matches the approved plan, including its known risks."
    else:
        avoidable = (
            "stockout" in actual.soft_issues and actual.lost_units > policy.verification.unacceptable_if_lost_units_over
        )
        deep_ss = actual.min_close < ss * policy.verification.degraded_ok_if_min_stock_over_ss_pct / 100
        if avoidable or actual.over_capacity_days or deep_ss:
            status = "UNACCEPTABLE"
            msg = (
                f"Real outcome is worse than planned: {actual.lost_units:g} lost units projected, minimum stock "
                f"{actual.min_close:g} vs safety stock {ss:g}. Remaining need ≈ {residual:g} units."
            )
        else:
            status, msg = "DEGRADED_OK", f"Stock dips to {actual.min_close:g} (safety stock {ss:g}) but no lost sales."
    return VerificationReport(
        status=status, message=msg, differences=diffs, expected=exp, actual=act, residual_need=residual
    )
