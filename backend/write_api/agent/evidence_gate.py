"""Evidence gate: before a decision is even validated, check the agent actually looked.

1. Required reads per decision type (e.g. you cannot modify a PO without checking open POs).
2. Grounding: every evidence id cited in the reasons must be a real, successful tool call of this run,
   and at least one reason must cite evidence.
"""

from shared.domain.decision import Decision

BUYING = {"get_inventory", "get_open_pos", "get_supplier_terms", "get_budget", "get_storage_status"}
REQUIRED: dict[str, set[str]] = {
    "accept": BUYING,
    "modify": BUYING,
    "reject": {"get_inventory", "get_open_pos"},
    "investigate": {"get_inventory"},
    "escalate": set(),
}


def check(decision: Decision, successful_calls: dict[str, str]) -> dict | None:
    """successful_calls: tool_call_id → tool name. Returns None if OK, else an error for the model."""
    called = set(successful_calls.values())
    missing = sorted(REQUIRED[decision.type] - called)
    cited = [e for r in decision.reasons for e in r.evidence]
    unknown = sorted({e for e in cited if e not in successful_calls})
    problems = {}
    if missing:
        problems["missing_tools"] = missing
    if unknown:
        problems["unknown_evidence_ids"] = unknown
    if not cited:
        problems["no_evidence"] = "no reason cites a tool_call id"
    if not problems:
        return None
    return {"error": "decision rejected by the evidence gate", **problems,
            "fix": "call the missing tools, cite real tool_call ids in reasons[].evidence, then submit again",
            "valid_tool_call_ids": successful_calls}
