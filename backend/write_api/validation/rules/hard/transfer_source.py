"""HARD: a transfer may only take what the other store can spare after covering its own need."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    ok = i.evaluation.checks.get("transfer_source", True)
    if not i.transfers:
        return RuleResult(rule="transfer_source", kind="hard", passed=True, message="no transfers")
    problems = [n for n in i.evaluation.notes if n.startswith("transfer")]
    return RuleResult(rule="transfer_source", kind="hard", passed=ok,
                      message="transfers within the other stores' surplus" if ok else "; ".join(problems))
