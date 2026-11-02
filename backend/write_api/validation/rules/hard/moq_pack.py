"""HARD: every line respects the supplier's MOQ, case pack and max quantity, and is > 0."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    c = i.evaluation.checks
    ok = c["moq"] and c["case_pack"] and c["max_qty"] and c["qty_positive"]
    problems = [n for n in i.evaluation.notes if "MOQ" in n or "case pack" in n]
    return RuleResult(
        rule="moq_case_pack",
        kind="hard",
        passed=ok,
        message="MOQ, case pack and max qty respected" if ok else "; ".join(problems) or "quantity invalid",
    )
