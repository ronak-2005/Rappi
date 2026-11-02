"""SOFT: plan value must fit the remaining budget (a human may approve an exception)."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ev, left = i.evaluation, i.ctx.budget_remaining
    ok = "budget" not in ev.soft_issues
    return RuleResult(rule="budget", kind="soft", passed=ok,
                      message=f"plan value {ev.purchase_cost:g} vs budget remaining "
                              f"{'unlimited' if left is None else f'{left:g}'}")
