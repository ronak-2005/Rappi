"""Code-based graders: did the agent decide correctly, gather the evidence, respect the rules, act,
verify, and recover? Each check is independent and explainable. Ground truth = fixture `expected`."""

from dataclasses import dataclass
from typing import Optional

from evals.harness import RunRecord


@dataclass
class Check:
    name: str
    group: str  # decision | evidence | constraints | action | validation | recovery
    passed: bool
    detail: str


def _initial_decision(r: RunRecord) -> Optional[dict]:
    """The decision that was acted on first (or the final one if nothing was executed)."""
    last = None
    for s in r.steps:
        if s["kind"] == "decision":
            last = s["payload"]
        if s["kind"] == "action":
            return last
    return r.run.get("decision") or last


def _qty(d: Optional[dict]) -> int:
    return sum(ln["qty"] for ln in (d or {}).get("lines", []) or [])


def grade(r: RunRecord) -> list[Check]:
    e, out = r.fixture.expected, []
    d = _initial_decision(r)
    dtype = (d or {}).get("type")
    add = lambda *a: out.append(Check(*a))  # noqa: E731

    add("decision_type", "decision", dtype in e.decision, f"got {dtype}, expected one of {e.decision}")
    if e.qty_range is not None:
        q = _qty(d)
        add("quantity", "decision", e.qty_range[0] <= q <= e.qty_range[1], f"got {q}, expected {list(e.qty_range)}")
    if e.lines is not None and dtype in ("accept", "modify"):
        n = len((d or {}).get("lines", []))
        add("order_lines", "decision", n == e.lines, f"got {n} line(s), expected {e.lines}")
    if e.supplier and dtype in ("accept", "modify"):
        sups = {ln["supplier_id"] for ln in d.get("lines", [])}
        add("supplier", "decision", sups == {e.supplier}, f"got {sorted(sups)}, expected {e.supplier}")

    ok_tools = {s["name"] for s in r.steps if s["kind"] == "tool_call" and s["payload"].get("ok")}
    missing = sorted(set(e.required_tools) - ok_tools)
    add("required_evidence", "evidence", not missing, "all required tools called" if not missing else f"missing {missing}")
    gate_fail = [s for s in r.steps if s["kind"] == "gate" and s["payload"].get("passed") is not True]
    add("evidence_gate_first_try", "evidence", not gate_fail, f"{len(gate_fail)} gate rejection(s)")

    actions = [i for i, s in enumerate(r.steps) if s["kind"] == "action"]
    unvalidated = [i for i in actions if not any(
        s["kind"] == "validation" and s["payload"].get("passed") for s in r.steps[:i])]
    add("validated_before_acting", "constraints", not unvalidated, f"{len(actions)} action(s), {len(unvalidated)} unvalidated")
    if e.approval_required is not None:
        add("approval_gate", "constraints", (r.approvals_requested > 0) == e.approval_required,
            f"approval requested {r.approvals_requested}x, expected {'yes' if e.approval_required else 'no'}")

    if e.pos_created is not None:
        add("purchase_orders", "action", len(r.agent_pos) == e.pos_created, f"{len(r.agent_pos)} PO(s), expected {e.pos_created}")
    keys = [p["idempotency_key"] for p in r.agent_pos]
    add("no_duplicate_orders", "action", len(keys) == len(set(keys)) and len(r.supplier_orders) == len(r.agent_pos),
        f"{len(r.agent_pos)} PO(s) here, {len(r.supplier_orders)} at the supplier")
    if e.supplier_orders is not None:
        add("supplier_side_orders", "action", len(r.supplier_orders) == e.supplier_orders,
            f"{len(r.supplier_orders)}, expected {e.supplier_orders}")

    unverified = [i for i in actions if not any(s["kind"] == "verification" for s in r.steps[i + 1:])]
    add("verified_after_acting", "validation", not unverified, f"{len(actions)} action(s), {len(unverified)} unverified")
    final_v = (r.run.get("outcome") or {}).get("final_verification")
    if e.final_verification:
        add("final_verification", "validation", final_v in e.final_verification,
            f"got {final_v}, expected {e.final_verification}")

    if e.recovery == "replan":
        add("recovered_by_replanning", "recovery", r.run["replans"] >= 1 and r.run["status"] == "completed",
            f"replans={r.run['replans']}, status={r.run['status']}")
        if e.replan_qty_range:
            extra = sum(p["qty_ordered"] for p in r.agent_pos[1:])
            add("replan_quantity", "recovery", e.replan_qty_range[0] <= extra <= e.replan_qty_range[1],
                f"re-ordered {extra}, expected {list(e.replan_qty_range)}")
    elif e.recovery == "escalate":
        add("escalated", "recovery", r.run["status"] == "escalated", f"status={r.run['status']}")
    add("run_finished_cleanly", "recovery", r.run["status"] in ("completed", "escalated") and not r.error,
        f"status={r.run['status']} error={r.error}")
    return out
