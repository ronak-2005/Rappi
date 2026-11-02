"""Every fixture file parses and loads into a fresh database."""

import pytest
from sqlmodel import select

from shared.db import models as m
from shared.db.session import read_only
from shared.domain.fixtures import list_fixture_files
from write_api.services.fixture_service import load_world

FIXTURES = list_fixture_files()


def test_fixtures_exist():
    assert len(FIXTURES) >= 11


@pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f.id)
def test_fixture_loads(fx, db_file):
    load_world(fx.id, db_file)
    with read_only(db_file) as s:
        world = s.exec(select(m.World)).one()
        assert world.fixture_id == fx.id
        assert s.exec(select(m.Inventory)).all()
        assert s.exec(select(m.SupplierTerm)).all()
        if fx.trigger.recommendation:
            rec = s.get(m.Recommendation, fx.trigger.recommendation.id)
            assert rec.qty == fx.trigger.recommendation.qty


def test_reload_replaces_previous_world(db_file):
    load_world("s1_reject_overstock", db_file)
    load_world("s1_accept", db_file)
    with read_only(db_file) as s:
        assert s.exec(select(m.World)).one().fixture_id == "s1_accept"
        assert s.exec(select(m.PurchaseOrder)).all() == []  # PO-2001 from the first world is gone


def test_sales_history_ends_yesterday(db_file):
    fx = load_world("s1_accept", db_file)
    with read_only(db_file) as s:
        days = sorted(r.day for r in s.exec(select(m.SalesHistory)).all())
    assert (fx.today - days[-1]).days == 1
    assert len(days) == 14
