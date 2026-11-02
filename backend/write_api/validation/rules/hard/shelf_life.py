"""HARD: projected expiry of the ordered units must stay under the policy limit."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ev, limit = i.evaluation, i.policy.hard_rules.max_expiry_waste_pct
    ok = ev.waste_pct <= limit
    return RuleResult(
        rule="shelf_life",
        kind="hard",
        passed=ok,
        message=f"projected expiry {ev.expired_units:g} units ({ev.waste_pct}%), limit {limit}%",
    )
