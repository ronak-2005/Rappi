"""GET: the latest evaluation report written by `make eval`."""

import json

from fastapi import APIRouter

from shared.config.settings import BACKEND_DIR

router = APIRouter(tags=["evals"])


@router.get("/evals/latest")
def latest():
    path = BACKEND_DIR / "evals" / "reports" / "report.json"
    if not path.exists():
        return {"available": False, "message": "no eval report yet — run `make eval`"}
    return {"available": True, **json.loads(path.read_text())}
