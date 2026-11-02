"""Every fixture (S1-S4) end-to-end with the deterministic baseline brain: same orchestrator, tools,
evidence gate, rulebook, gateway, mock supplier and verifier as a live LLM run. No API key."""

import pytest

from evals.graders import grade
from evals.harness import run_fixture
from shared.domain.fixtures import list_fixture_files

FIXTURES = [f.id for f in list_fixture_files()]


@pytest.mark.parametrize("fixture_id", FIXTURES)
def test_baseline_passes_every_check(fixture_id, db_file):
    record = run_fixture(fixture_id, db_file)
    failed = [f"{c.name}: {c.detail}" for c in grade(record) if not c.passed]
    assert not failed, failed
