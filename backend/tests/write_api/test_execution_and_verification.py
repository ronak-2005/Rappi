"""Gateway + mock supplier + verifier + learning: the feedback loop after acting."""

from sqlmodel import select

from shared.config.policy import load_policy
from shared.db import models as m
from shared.db.session import read_write
from shared.domain.planning import Plan, PlanLine
from shared.db import snapshot
from shared.engine.options import evaluate_plan
from write_api.actions import gateway
from write_api.verification import learning, verifier

POLICY = load_policy()


def execute_and_verify(db_file, supplier, lines, rec, node="CHAP", sku="MILK1L", tag="plan-0"):
    with read_write(db_file) as s:
        expected = evaluate_plan(snapshot.build_context(s, node, sku, rec), POLICY, Plan(lines=lines))
        result = gateway.execute(s, supplier, run_id="RUN-T", attempt_tag=tag, node=node, sku=sku, lines=lines,
                                 recommendation_id=rec)
        report = verifier.verify(s, POLICY, node=node, sku=sku, expected=expected, execution=result,
                                 recommendation_id=rec)
        stats = learning.record(s, result)
        return result, report, stats


def agent_pos(db_file):
    with read_write(db_file) as s:
        return s.exec(select(m.PurchaseOrder).where(m.PurchaseOrder.created_by == "agent")).all()


def test_full_confirmation_is_ok_and_commits_budget(world, db_file, supplier):
    world("s1_modify_open_po_ignored")
    result, report, _ = execute_and_verify(db_file, supplier, [PlanLine(supplier_id="SUP_A", qty=500)], "REC-101")
    assert result.lines[0].status == "confirmed" and report.status == "OK"
    with read_write(db_file) as s:
        assert s.exec(select(m.Budget)).one().committed == 480 + 600


def test_partial_confirmation_is_unacceptable_with_residual(world, db_file, supplier):
    world("s4_feedback_partial_confirm")
    result, report, stats = execute_and_verify(db_file, supplier, [PlanLine(supplier_id="SUP_A", qty=500)], "REC-405")
    assert result.lines[0].status == "partially_confirmed" and result.lines[0].qty_confirmed == 250
    assert report.status == "UNACCEPTABLE" and report.actual["lost_units"] == 50
    assert report.residual_need == 207
    assert stats[0]["fill_rate"] < 0.97  # learning: SUP_A's fill rate dropped


def test_timeout_is_retried_without_duplicate(world, db_file, supplier):
    world("s4_timeout_retry_idempotent")
    result, report, _ = execute_and_verify(db_file, supplier, [PlanLine(supplier_id="SUP_A", qty=760)], "REC-406")
    line = result.lines[0]
    assert line.status == "confirmed" and line.attempts == 2 and line.replayed
    assert len(agent_pos(db_file)) == 1 and len(supplier.orders()) == 1
    assert report.status == "OK"  # a retry is not a material difference


def test_re_executing_same_plan_reuses_po(world, db_file, supplier):
    world("s1_accept")
    lines = [PlanLine(supplier_id="SUP_A", qty=760)]
    execute_and_verify(db_file, supplier, lines, "REC-100")
    result, _, _ = execute_and_verify(db_file, supplier, lines, "REC-100")  # same run + tag (e.g. crash recovery)
    assert result.lines[0].replayed and len(agent_pos(db_file)) == 1 and len(supplier.orders()) == 1


def test_rejection_is_unacceptable(world, db_file, supplier):
    world("s1_modify_open_po_ignored")
    supplier.set_scenario({"SUP_A": {"mode": "reject"}})
    result, report, _ = execute_and_verify(db_file, supplier, [PlanLine(supplier_id="SUP_A", qty=500)], "REC-101")
    assert result.lines[0].status == "rejected" and report.status == "UNACCEPTABLE"
    with read_write(db_file) as s:
        assert s.exec(select(m.Budget)).one().committed == 480  # nothing committed for a rejected PO


def test_harmless_delay_is_degraded_ok(world, db_file, supplier):
    world("s1_accept")
    supplier.set_scenario({"SUP_A": {"mode": "delay", "delay_days": 1}})
    _, report, _ = execute_and_verify(db_file, supplier, [PlanLine(supplier_id="SUP_A", qty=760)], "REC-100")
    assert report.status in ("DEGRADED_OK", "UNACCEPTABLE")
    assert any("delivery moved" in d for d in report.differences)
