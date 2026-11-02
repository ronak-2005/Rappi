"""Shared objects for write-side controllers: DB file, Read API client, supplier client."""

from fastapi import Request

from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient


def db_file(request: Request):
    return request.app.state.db_file


def read_client(request: Request) -> ReadApiClient:
    return request.app.state.read_client


def supplier_client(request: Request) -> SupplierClient:
    return request.app.state.supplier_client
