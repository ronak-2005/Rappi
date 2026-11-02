"""HARD: each delivery day is possible (not before the earliest arrival, on a delivery weekday)."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ok = i.evaluation.checks["delivery_calendar"]
    problems = [n for n in i.evaluation.notes if "delivery day" in n]
    return RuleResult(
        rule="delivery_calendar",
        kind="hard",
        passed=ok,
        message="delivery dates feasible" if ok else "; ".join(problems),
    )
