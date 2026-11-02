"""SOFT: ordering from a supplier with a poor fill rate needs a human."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ok = "supplier_reliability" not in i.evaluation.soft_issues
    rates = {o.supplier_id: o.fill_rate for o in i.ctx.offers if o.supplier_id in {ln.supplier_id for ln in i.lines}}
    return RuleResult(
        rule="supplier_reliability",
        kind="soft",
        passed=ok,
        message=f"fill rates {rates}, minimum {i.policy.soft_rules.min_supplier_fill_rate}",
    )
