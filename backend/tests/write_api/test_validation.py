"""The rulebook: hard rules block, soft rules ask for approval, verdicts name the rule."""

from shared.config.policy import load_policy
from shared.db.session import read_write
from shared.domain.planning import PlanLine
from write_api.validation.validator import validate

POLICY = load_policy()


def run(db_file, lines, rec="REC-101", node="CHAP", sku="MILK1L"):
    with read_write(db_file) as s:
        return validate(s, POLICY, node, sku, lines, rec)


def names(results):
    return {r.rule for r in results}


def test_recommended_800_is_blocked(world, db_file):
    world("s1_modify_open_po_ignored")
    r = run(db_file, [PlanLine(supplier_id="SUP_A", qty=800)])
    assert not r.passed and names(r.hard_failures) == {"storage_capacity", "shelf_life"}  # 100 of 800 would expire
    assert "budget" in names(r.soft_violations)


def test_correct_500_passes_cleanly(world, db_file):
    world("s1_modify_open_po_ignored")
    r = run(db_file, [PlanLine(supplier_id="SUP_A", qty=500)])
    assert r.passed and not r.requires_approval


def test_moq_and_case_pack(world, db_file):
    world("s1_modify_open_po_ignored")
    r = run(db_file, [PlanLine(supplier_id="SUP_A", qty=450)])
    assert "moq_case_pack" in names(r.hard_failures)


def test_express_needs_express_offer(world, db_file):
    world("s4_storage_two_drops")  # SUP_A has no express here
    r = run(db_file, [PlanLine(supplier_id="SUP_A", qty=700, mode="express")], rec="REC-401")
    assert "supplier" in names(r.hard_failures)


def test_budget_is_soft(world, db_file):
    world("s4_budget_partial_needs_approval")
    r = run(db_file, [PlanLine(supplier_id="SUP_A", qty=760)], rec="REC-402")
    assert r.passed and r.requires_approval and names(r.soft_violations) == {"budget"}


def test_reject_with_stockout_needs_approval(world, db_file):
    world("s4_moq_exceeds_shelf_life")
    r = run(db_file, [], rec="REC-404", sku="YOG150")
    assert r.passed and "avoidable_stockout" in names(r.soft_violations)


def test_duplicate_po_is_hard(world, db_file):
    world("s1_reject_overstock")  # PO-2001: 1200 from SUP_A arriving day 1
    from datetime import date
    from shared.db import models as m
    with read_write(db_file) as s:  # an identical open PO for day 3
        s.add(m.PurchaseOrder(id="PO-X", node_id="CHAP", sku_id="MILK1L", supplier_id="SUP_A", qty_ordered=500,
                              unit_cost=1.2, status="sent", order_date=date(2026, 11, 2),
                              expected_delivery=date(2026, 11, 5)))
        s.commit()
    r = run(db_file, [PlanLine(supplier_id="SUP_A", qty=500)], rec="REC-102")
    assert "no_duplicate_po" in names(r.hard_failures)
