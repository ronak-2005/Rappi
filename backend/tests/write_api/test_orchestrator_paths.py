"""Orchestrator edge paths driven by a ScriptedLLM (exact, zero-cost): what happens when the model
misbehaves, a rule blocks the plan, or a human must decide."""

import pytest
from fastapi.testclient import TestClient
from sqlmodel import select

from mock_supplier.server.main import create_app as create_supplier
from read_api.server.main import create_app as create_read
from shared.config.llm_settings import LLMSettings
from shared.db import models as m
from shared.db.session import read_write
from write_api.agent.orchestrator import Orchestrator
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.llm.client import LLMResponse
from write_api.llm.scripted import ScriptedLLM, call
from write_api.services import fixture_service, run_service

FACTS = ["get_situation", "get_inventory", "get_open_pos", "get_supplier_terms", "get_budget", "get_storage_status"]


def facts():
    return [call(n, {}, f"c_{n}") for n in FACTS]


def decision(qty, typ="modify", evidence=("c_get_inventory", "c_get_open_pos")):
    return {"type": typ, "lines": [{"supplier_id": "SUP_A", "qty": qty}] if qty else [],
            "reasons": [{"factor": "requirement", "finding": "see tools", "evidence": list(evidence)}],
            "summary": f"buy {qty}"}


@pytest.fixture
def stack(db_file):
    def _make(fixture_id, steps, approver=None):
        read = ReadApiClient(TestClient(create_read(db_file)))
        supplier = SupplierClient(TestClient(create_supplier()))
        fx = fixture_service.load_world(fixture_id, db_file, supplier)
        deps = run_service.make_deps(db_file=db_file, read=read, supplier=supplier,
                                     llm_settings=LLMSettings(llm_mode="baseline"), approver=approver)
        deps.llm = ScriptedLLM(steps)
        orch = Orchestrator(deps)
        run_id = orch.start(fx.trigger.recommendation.id)
        return orch, run_id, deps
    return _make


def steps_of(db_file, run_id, kind=None):
    with read_write(db_file) as s:
        q = select(m.TraceStep).where(m.TraceStep.run_id == run_id).order_by(m.TraceStep.seq)
        return [x for x in s.exec(q).all() if kind is None or x.kind == kind]


def pos(db_file):
    with read_write(db_file) as s:
        return s.exec(select(m.PurchaseOrder).where(m.PurchaseOrder.created_by == "agent")).all()


def test_rulebook_rejection_then_revision(stack, db_file):
    orch, run_id, _ = stack("s1_modify_open_po_ignored",
                            facts() + [call("submit_decision", decision(800)), call("submit_decision", decision(500))])
    run = orch.run(run_id)
    assert run.status == "completed" and run.revisions == 1
    v = steps_of(db_file, run_id, "validation")
    assert v[0].payload["passed"] is False and v[1].payload["passed"] is True
    assert [p.qty_ordered for p in pos(db_file)] == [500]  # the blocked 800 was never ordered


def test_missing_evidence_is_sent_back(stack, db_file):
    orch, run_id, _ = stack("s1_modify_open_po_ignored", [
        call("get_inventory", {}, "c_get_inventory"),
        call("submit_decision", decision(500, evidence=("c_get_inventory",))),  # skipped open POs etc.
        *facts(), call("submit_decision", decision(500))])
    run = orch.run(run_id)
    gate = steps_of(db_file, run_id, "gate")
    assert "get_open_pos" in gate[0].payload["missing_tools"]
    assert run.status == "completed" and len(pos(db_file)) == 1


def test_hallucinated_evidence_id_is_rejected(stack, db_file):
    orch, run_id, _ = stack("s1_modify_open_po_ignored",
                            facts() + [call("submit_decision", decision(500, evidence=("call_made_up",))),
                                       call("submit_decision", decision(500))])
    orch.run(run_id)
    assert steps_of(db_file, run_id, "gate")[0].payload["unknown_evidence_ids"] == ["call_made_up"]


def test_invalid_json_and_schema_errors_are_recoverable(stack, db_file):
    orch, run_id, _ = stack("s1_modify_open_po_ignored", facts() + [
        call("submit_decision", "{not json"),
        call("submit_decision", {"type": "modify", "lines": [], "reasons": [], "summary": "x"}),
        call("submit_decision", decision(500))])
    run = orch.run(run_id)
    assert run.status == "completed"
    assert len(steps_of(db_file, run_id, "gate")) >= 2


def test_model_that_stops_calling_tools_is_escalated(stack):
    orch, run_id, _ = stack("s1_accept", [LLMResponse(text="I think it's fine.")] * 5)
    run = orch.run(run_id)
    assert run.status == "escalated" and "stopped calling tools" in run.decision["summary"]


def test_tool_budget_is_enforced(stack):
    orch, run_id, deps = stack("s1_accept", [call("get_inventory", {}, f"c{i}") for i in range(40)])
    run = orch.run(run_id)
    assert run.status == "escalated" and run.tool_calls == deps.policy.loop_limits.max_tool_calls
    warned = [m for m in run.memory["messages"] if m["role"] == "tool" and "budget_warning" in m["content"]]
    assert len(warned) == 6  # warned at 5, 4, 3, 2, 1 and 0 calls left


def test_unknown_tool_does_not_crash(stack, db_file):
    orch, run_id, _ = stack("s1_accept", [call("place_order_directly", {"qty": 9999})] + facts()
                            + [call("submit_decision", decision(760, typ="accept"))])
    run = orch.run(run_id)
    assert run.status == "completed" and [p.qty_ordered for p in pos(db_file)] == [760]


def test_pause_for_approval_then_resume(stack, db_file):
    orch, run_id, deps = stack("s4_budget_partial_needs_approval",
                               facts() + [call("submit_decision", decision(760, typ="accept"))])
    run = orch.run(run_id)
    assert run.status == "awaiting_approval" and pos(db_file) == []  # nothing ordered before a human says yes
    with read_write(db_file) as s:
        approval = s.exec(select(m.Approval)).one()
    assert any("budget" in r for r in approval.reasons)
    run_service.resolve_approval(deps, approval.id, "approve", "buyer", "ok, exception granted", None)
    run = orch.resume(run_id)
    assert run.status == "completed" and [p.qty_ordered for p in pos(db_file)] == [760]


def test_human_edit_is_still_checked_by_hard_rules(stack, db_file):
    orch, run_id, deps = stack("s4_budget_partial_needs_approval",
                               facts() + [call("submit_decision", decision(760, typ="accept"))])
    orch.run(run_id)
    with read_write(db_file) as s:
        approval = s.exec(select(m.Approval)).one()
    run_service.resolve_approval(deps, approval.id, "edit", "buyer", "", [{"supplier_id": "SUP_A", "qty": 450}])
    run = orch.resume(run_id)
    assert run.status == "escalated" and pos(db_file) == []  # 450 < MOQ 500: even a human can't break hard rules


def test_human_rejection_goes_back_to_the_agent(stack, db_file):
    orch, run_id, deps = stack("s4_budget_partial_needs_approval",
                               facts() + [call("submit_decision", decision(760, typ="accept")),
                                          call("escalate", {"reason": "buyer refused the budget exception"})])
    orch.run(run_id)
    with read_write(db_file) as s:
        approval = s.exec(select(m.Approval)).one()
    run_service.resolve_approval(deps, approval.id, "reject", "buyer", "no budget exceptions this month", None)
    run = orch.resume(run_id)
    assert run.status == "escalated" and pos(db_file) == []
    assert any("no budget exceptions" in (msg.get("content") or "") for msg in run.memory["messages"])


def test_tool_call_written_as_text_is_recovered():
    from write_api.llm.openai_compat import _calls_from_text
    calls = _calls_from_text('Sure. {"name": "get_inventory", "arguments": {"node": "CHAP"}} done',
                             {"get_inventory", "submit_decision"})
    assert [(c.name, c.arguments) for c in calls] == [("get_inventory", '{"node": "CHAP"}')]
    assert _calls_from_text('{"name": "rm_rf", "arguments": {}}', {"get_inventory"}) == []


def test_provider_extra_fields_round_trip():
    from write_api.agent.orchestrator import _assistant_message
    from write_api.llm.client import LLMResponse, ToolCall
    sig = {"extra_content": {"google": {"thought_signature": "abc"}}}
    msg = _assistant_message(LLMResponse(tool_calls=[ToolCall(id="c1", name="get_inventory", arguments="{}", extra=sig)]))
    assert msg["tool_calls"][0]["extra_content"] == sig["extra_content"]  # sent back unchanged next turn
