"""Read API end-to-end over HTTP (in-process), against a loaded fixture world."""

import pytest
from fastapi.testclient import TestClient

from read_api.server.main import create_app
from write_api.services.fixture_service import load_world


@pytest.fixture
def client(db_file):
    load_world("s1_modify_open_po_ignored", db_file)
    return TestClient(create_app(db_file))


def test_health_and_world(client):
    assert client.get("/health").json()["world_loaded"] == "s1_modify_open_po_ignored"
    w = client.get("/world").json()
    assert w["today"] == "2026-11-02" and w["weekday"] == "Monday"


def test_facts(client):
    assert client.get("/situation/recommendations/REC-101").json()["recommendation"]["qty"] == 800
    inv = client.get("/nodes/CHAP/skus/MILK1L/inventory").json()
    assert inv["on_hand"] == 300 and inv["last_counted_days_ago"] == 1
    pos = client.get("/nodes/CHAP/skus/MILK1L/purchase-orders/open").json()["open_purchase_orders"]
    assert [(p["id"], p["arrives_in_days"]) for p in pos] == [("PO-1001", 2)]
    sup = client.get("/skus/MILK1L/suppliers").json()["suppliers"][0]
    assert sup["moq"] == 500 and sup["earliest_standard_arrival_in_days"] == 3
    assert client.get("/nodes/CHAP/budget", params={"category": "dairy"}).json()["remaining"] == 700
    st = client.get("/nodes/CHAP/storage/chilled").json()
    assert st["free_for_this_sku_l_by_day"][3]["free_l"] == 900
    assert len(client.get("/nodes/CHAP/skus/MILK1L/sales").json()["daily"]) == 14


def test_planning(client):
    req = client.get("/nodes/CHAP/skus/MILK1L/requirement", params={"recommendation_id": "REC-101"}).json()
    assert req["net_requirement"] == 457 and req["order_qty"] == 500 and req["arrival_date"] == "2026-11-05"
    opts = client.get("/nodes/CHAP/skus/MILK1L/options", params={"recommendation_id": "REC-101"}).json()["options"]
    assert opts[0]["total_qty"] == 500 and opts[0]["hard_ok"]
    plan = {"plan": {"lines": [{"supplier_id": "SUP_A", "qty": 800}]}, "recommendation_id": "REC-101"}
    ev = client.post("/nodes/CHAP/skus/MILK1L/evaluate", json=plan).json()
    assert ev["checks"]["capacity"] is False and "budget" in ev["soft_issues"]
    proj = client.post("/nodes/CHAP/skus/MILK1L/projection", json=plan).json()
    assert proj["days"][3]["available"] == 1200 and proj["days"][3]["over_capacity"]
    dq = client.get("/nodes/CHAP/skus/MILK1L/data-quality").json()
    assert dq["ok"] is True


def test_phantom_stock_flags(db_file):
    load_world("s1_investigate_phantom_stock", db_file)
    dq = TestClient(create_app(db_file)).get("/nodes/CHAP/skus/MILK1L/data-quality").json()
    assert {a["code"] for a in dq["anomalies"]} == {"sales_while_zero_stock", "stale_count"}


def test_errors_are_json_with_component(client):
    r = client.get("/skus/NOPE")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found" and r.json()["error"]["service"] == "read_api"


def test_fixture_catalogue(client):
    ids = {f["id"] for f in client.get("/fixtures").json()}
    assert "s4_storage_two_drops" in ids


def test_no_world_loaded_is_a_clear_error(db_file):
    r = TestClient(create_app(db_file)).get("/world")
    assert r.status_code == 404 and "load a fixture" in r.json()["error"]["message"]
