"""HTTP plumbing reused by every service's server/: request-id middleware and JSON error responses."""

import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from shared.domain.errors import DomainError
from shared.observability.logging import request_id_var, run_id_var

log = logging.getLogger("shared.observability.http")


def install_request_context(app: FastAPI) -> None:
    @app.middleware("http")
    async def _ctx(request: Request, call_next):
        rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
        request_id_var.set(rid)
        run_id_var.set(request.headers.get("x-run-id", ""))
        start = time.perf_counter()
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        log.info("%s %s → %s (%.0f ms)", request.method, request.url.path, response.status_code,
                 (time.perf_counter() - start) * 1000)
        return response


def install_error_handlers(app: FastAPI, service: str) -> None:
    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError):
        return JSONResponse(status_code=exc.status, content={"error": {
            "code": exc.code, "service": service, "component": exc.component, "message": exc.message}})

    @app.exception_handler(Exception)
    async def _unexpected(request: Request, exc: Exception):
        log.exception("unhandled error on %s", request.url.path)
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "service": service, "component": type(exc).__module__,
            "message": f"{type(exc).__name__}: {exc}"}})
