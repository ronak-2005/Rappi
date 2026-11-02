"""Write-side test helpers: a mock supplier served in-process and a loader for fixture worlds."""

import pytest
from fastapi.testclient import TestClient

from mock_supplier.server.main import create_app as create_supplier
from write_api.clients.supplier_client import SupplierClient
from write_api.services.fixture_service import load_world


@pytest.fixture
def supplier():
    return SupplierClient(TestClient(create_supplier()))


@pytest.fixture
def world(db_file, supplier):
    def _load(fixture_id: str):
        return load_world(fixture_id, db_file, supplier)
    return _load
