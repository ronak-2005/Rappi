"""Write API process (port 8002): the only service that changes state. Hosts the agent.

Run: uvicorn write_api.server.main:app --port 8002
"""

from fastapi import FastAPI

from shared.config.settings import get_settings
from shared.db.session import write_engine
from shared.observability.http import install_common
from shared.observability.logging import setup_logging
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.controllers import approvals, events, fixtures, runs
from write_api.server.health import router as health_router

SERVICE = "write_api"


def create_app(
    db_file: str | None = None, read_client: ReadApiClient | None = None, supplier_client: SupplierClient | None = None
) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Purchasing Agent — Write API",
        version="0.1.0",
        description="Commands only. Every change goes through validation, approval, idempotent execution and verification.",
    )
    write_engine(db_file)  # make sure the schema exists
    app.state.db_file = db_file
    app.state.read_client = read_client or ReadApiClient.from_url(settings.read_api_url)
    app.state.supplier_client = supplier_client or SupplierClient.from_url(settings.supplier_api_url)
    install_common(app, SERVICE, settings.cors_origins)
    for r in (health_router, fixtures.router, runs.router, approvals.router, events.router):
        app.include_router(r)
    return app


def _build() -> FastAPI:
    settings = get_settings()
    setup_logging(SERVICE, settings.log_level, settings.var_dir / "logs")
    return create_app()


app = _build()
