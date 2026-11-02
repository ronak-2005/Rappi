"""HARD: never place a PO identical to one that is already open (same supplier, qty, delivery date)."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    d = i.duplicate_po_ids
    return RuleResult(rule="no_duplicate_po", kind="hard", passed=not d,
                      message="no identical open PO" if not d else f"identical open PO(s) already exist: {d}")
