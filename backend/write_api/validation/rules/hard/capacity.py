"""HARD: the plan must not overflow the storage zone on any day."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    days = i.evaluation.over_capacity_days
    return RuleResult(
        rule="storage_capacity",
        kind="hard",
        passed=not days,
        message="fits storage on every day" if not days else f"storage overflows on day(s) {days} (relative to today)",
    )
