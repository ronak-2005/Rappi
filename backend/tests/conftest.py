"""Shared test fixtures: a throw-away SQLite file per test."""

import pytest


@pytest.fixture
def db_file(tmp_path):
    return str(tmp_path / "test.db")
