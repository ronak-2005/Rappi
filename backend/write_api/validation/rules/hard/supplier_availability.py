"""HARD: don't order more from a supplier than it told us it can supply right now (Scenario 2)."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ok = i.evaluation.checks.get("supplier_availability", True)
    problems = [n for n in i.evaluation.notes if "can only supply" in n]
    return RuleResult(rule="supplier_availability", kind="hard", passed=ok,
                      message="within what suppliers can supply" if ok else "; ".join(problems))
