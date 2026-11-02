"""The read-only session must make writes impossible at the database level."""

from datetime import date

import pytest
from sqlalchemy.exc import OperationalError

from shared.db import models as m
from shared.db.session import read_only, read_write


def test_read_only_session_rejects_writes(db_file):
    with read_write(db_file) as s:
        s.add(m.Node(id="A", name="a"))
        s.commit()
    with read_only(db_file) as s:
        assert s.get(m.Node, "A").name == "a"
        s.add(m.Node(id="B", name="b"))
        with pytest.raises(OperationalError, match="readonly"):
            s.commit()


def test_read_write_session_writes(db_file):
    with read_write(db_file) as s:
        s.add(m.World(fixture_id="x", today=date(2026, 11, 2)))
        s.commit()
    with read_only(db_file) as s:
        assert s.get(m.World, 1).fixture_id == "x"
