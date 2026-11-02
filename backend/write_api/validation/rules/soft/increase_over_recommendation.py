"""SOFT: buying much MORE than the system recommended needs a human. Buying less is fine when the
projection proves coverage (the other rules check that)."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    rec, qty = i.ctx.recommendation_qty, i.evaluation.total_qty
    pct = i.policy.soft_rules.increase_over_recommendation_pct
    ok = "increase_over_recommendation" not in i.evaluation.soft_issues
    msg = "no recommendation to compare" if not rec else f"plan {qty} vs recommendation {rec} (limit +{pct:g}%)"
    return RuleResult(rule="increase_over_recommendation", kind="soft", passed=ok, message=msg)
