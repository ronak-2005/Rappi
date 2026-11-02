"""SOFT: large plans need a human sign-off."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    v, limit = i.evaluation.purchase_cost, i.policy.soft_rules.po_value_over
    return RuleResult(rule="po_value", kind="soft", passed=v <= limit, message=f"plan value {v:g}, limit {limit:g}")
