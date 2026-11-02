"""Engine + snapshot reproduce the hand-computed answers of the S2/S3 fixtures (availability, transfers,
demand signal and demand assumptions all come from the database)."""

from shared.config.policy import load_policy
from shared.db import snapshot
from shared.db.session import read_write
from shared.domain.planning import DemandAssumption
from shared.engine.options import generate_options, requirement

POLICY = load_policy()


def ctx(db_file, demand=None):
    with read_write(db_file) as s:
        return snapshot.build_context(s, "CHAP", "MILK1L", demand_assumption=demand)


def signal(db_file):
    with read_write(db_file) as s:
        return snapshot.demand_signal(s, "CHAP", "MILK1L")


def test_supplier_event_marks_supplier_unavailable(world, db_file):
    world("s2_alt_supplier")
    c = ctx(db_file)
    sup_a = next(o for o in c.offers if o.supplier_id == "SUP_A")
    assert sup_a.available_qty == 0 and "250 of the 500" in sup_a.availability_note
    assert [r.qty for r in c.open_receipts] == [250]  # PO-3001 now counts its confirmed qty only


def test_s2_partial_but_sufficient(world, db_file):
    world("s2_partial_but_sufficient")
    c = ctx(db_file)
    assert requirement(c, POLICY).net_requirement == -43
    best = generate_options(c, POLICY)[0]
    assert best.kind == "do_nothing" and best.hard_ok and not best.soft_issues


def test_s2_transfer_from_node(world, db_file):
    world("s2_transfer_from_node")
    c = ctx(db_file)
    assert [(t.node_id, t.surplus) for t in c.transfer_sources] == [("USAQ", 1069)]
    best = generate_options(c, POLICY)[0]
    assert best.kind == "transfer" and best.transfer_qty == 607 and best.hard_ok and not best.soft_issues
    assert best.end_close == 157
    sup_b = next(o for o in generate_options(c, POLICY) if o.id == "standard:SUP_B")
    assert "stockout" in sup_b.soft_issues
    assert not any(o.id.startswith("standard:SUP_A") for o in generate_options(c, POLICY))  # unavailable


def test_s2_alt_supplier(world, db_file):
    world("s2_alt_supplier")
    c = ctx(db_file)
    assert c.transfer_sources[0].surplus == 0
    best = generate_options(c, POLICY)[0]
    assert best.id == "standard:SUP_B" and best.total_qty == 620 and best.hard_ok and not best.soft_issues
    assert best.end_close == 170


def test_s3_sustained_spike(world, db_file):
    world("s3_sustained_spike")
    sig = signal(db_file)
    assert sig.classification == "sustained_increase" and sig.recent_7d_avg == 180
    c = ctx(db_file, sig.suggested_assumption)
    assert requirement(c, POLICY).net_requirement == 1157
    best = generate_options(c, POLICY)[0]
    assert best.total_qty == 1160 and best.hard_ok and not best.soft_issues and best.end_close == 160
    naive = requirement(ctx(db_file), POLICY)  # on the forecast
    assert naive.order_qty == 500


def test_s3_promo_spike_temporary(world, db_file):
    world("s3_promo_spike_temporary")
    sig = signal(db_file)
    assert sig.classification == "promotion"
    assert sig.suggested_assumption == DemandAssumption(per_day=160, until_day=1, reason=sig.suggested_assumption.reason)
    assert requirement(ctx(db_file, sig.suggested_assumption), POLICY).net_requirement == -33
    overreact = requirement(ctx(db_file, DemandAssumption(per_day=160)), POLICY)
    assert overreact.net_requirement == 507


def test_s3_one_day_noise(world, db_file):
    world("s3_one_day_noise")
    sig = signal(db_file)
    assert sig.classification == "one_off_spike" and sig.suggested_assumption is None
    assert requirement(ctx(db_file), POLICY).net_requirement == -43
