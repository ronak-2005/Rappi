"""HARD: each line's supplier sells this SKU, is active, and offers express if express is requested."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    c = i.evaluation.checks
    ok = c["supplier_known"] and c["supplier_active"] and c["express_available"]
    problems = [n for n in i.evaluation.notes if "supplier" in n or "express" in n]
    return RuleResult(rule="supplier", kind="hard", passed=ok,
                      message="suppliers valid" if ok else "; ".join(problems) or "supplier inactive")
