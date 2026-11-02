"""SOFT: stock should stay at or above safety stock after the first delivery."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ev = i.evaluation
    ok = not ev.below_ss_days
    return RuleResult(
        rule="below_safety_stock",
        kind="soft",
        passed=ok,
        message=f"minimum stock {ev.min_close:g}"
        + ("" if ok else f", below safety stock on day(s) {ev.below_ss_days}"),
    )
