"""Write API process (port 8002): the only service that changes state. Hosts the agent.

Run: uvicorn write_api.server.main:app --port 8002
"""

from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from shared.config.settings import get_settings
from shared.db.session import write_engine
from shared.observability.http import install_error_handlers, install_request_context
from shared.observability.logging import setup_logging
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.controllers import approvals, fixtures, runs
from write_api.server.health import router as health_router

SERVICE = "write_api"


def create_app(db_file: Optional[str] = None, read_client: Optional[ReadApiClient] = None,
               supplier_client: Optional[SupplierClient] = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Purchasing Agent — Write API", version="0.1.0",
                  description="Commands only. Every change goes through validation, approval, idempotent execution and verification.")
    write_engine(db_file)  # make sure the schema exists
    app.state.db_file = db_file
    app.state.read_client = read_client or ReadApiClient.from_url(settings.read_api_url)
    app.state.supplier_client = supplier_client or SupplierClient.from_url(settings.supplier_api_url)
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins.split(","), allow_methods=["*"],
                       allow_headers=["*"])
    install_request_context(app)
    install_error_handlers(app, SERVICE)
    for r in (health_router, fixtures.router, runs.router, approvals.router):
        app.include_router(r)
    return app


def _build() -> FastAPI:
    settings = get_settings()
    setup_logging(SERVICE, settings.log_level, settings.var_dir / "logs")
    return create_app()


app = _build()
