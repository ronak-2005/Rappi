"""Write API over HTTP: load a scenario, start a run, approve, and read the results from the Read API."""

import pytest
from fastapi.testclient import TestClient

from mock_supplier.server.main import create_app as create_supplier
from read_api.server.main import create_app as create_read
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.server.main import create_app as create_write


@pytest.fixture
def apis(db_file):
    read_http = TestClient(create_read(db_file))
    write = TestClient(create_write(db_file, ReadApiClient(read_http), SupplierClient(TestClient(create_supplier()))))
    return read_http, write


def test_run_to_completion(apis):
    read, write = apis
    r = write.post("/runs", json={"fixture_id": "s1_modify_open_po_ignored", "llm_mode": "baseline"}).json()
    run = read.get(f"/runs/{r['run_id']}").json()  # background task already ran inside TestClient
    assert run["status"] == "completed" and run["decision"]["type"] == "modify"
    assert [p["qty_ordered"] for p in run["purchase_orders"]] == [500]
    assert read.get("/recommendations").json()[0]["status"] == "modified"
    trace = read.get(f"/runs/{r['run_id']}/trace").json()
    kinds = [s["kind"] for s in trace]
    assert kinds.index("validation") < kinds.index("action") < kinds.index("verification")


def test_approval_over_http(apis):
    read, write = apis
    r = write.post("/runs", json={"fixture_id": "s4_budget_partial_needs_approval", "llm_mode": "baseline"}).json()
    assert read.get(f"/runs/{r['run_id']}").json()["status"] == "awaiting_approval"
    pending = read.get("/approvals", params={"status": "pending"}).json()
    assert len(pending) == 1
    ok = write.post(f"/approvals/{pending[0]['id']}", json={"decision": "approve", "comment": "fine"}).json()
    assert ok["resuming"]
    run = read.get(f"/runs/{r['run_id']}").json()
    assert run["status"] == "completed" and run["approvals"][0]["status"] == "approved"
    again = write.post(f"/approvals/{pending[0]['id']}", json={"decision": "approve"})
    assert again.status_code == 409  # can't approve twice


def test_llm_health_without_key(apis):
    _, write = apis
    h = write.get("/health/llm", params={"env": "llm.env.example"}).json()
    assert h["mode"] == "live" and h["ok"] is False and "error" in h  # example file has no key → clear error


def test_unknown_fixture_is_404(apis):
    _, write = apis
    assert write.post("/fixtures/nope/load").status_code == 404
