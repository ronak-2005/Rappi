"""Read API process (port 8001). Every endpoint is a query; the DB is opened read-only.

Run: uvicorn read_api.server.main:app --port 8001
"""

from fastapi import FastAPI

from read_api.controllers import evals, facts, planning, runs, world
from read_api.server.health import router as health_router
from shared.config.settings import get_settings
from shared.observability.http import install_common
from shared.observability.logging import setup_logging

SERVICE = "read_api"


def create_app(db_file: str | None = None) -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Purchasing Agent — Read API",
        version="0.1.0",
        description="Queries only. The database connection is read-only.",
    )
    app.state.db_file = db_file
    install_common(app, SERVICE, settings.cors_origins)
    for r in (health_router, world.router, facts.router, planning.router, runs.router, evals.router):
        app.include_router(r)
    return app


def _build() -> FastAPI:
    settings = get_settings()
    setup_logging(SERVICE, settings.log_level, settings.var_dir / "logs")
    return create_app()


app = _build()
