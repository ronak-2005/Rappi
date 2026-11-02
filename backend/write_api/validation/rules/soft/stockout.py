"""SOFT: the plan should avoid lost sales that a supplier could have prevented."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ev = i.evaluation
    ok = "stockout" not in ev.soft_issues
    return RuleResult(
        rule="avoidable_stockout",
        kind="soft",
        passed=ok,
        message="no avoidable lost sales" if ok else f"{ev.lost_units:g} units of lost sales projected",
    )
