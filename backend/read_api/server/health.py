"""GET /health: is the read API up and can it read the database?"""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from read_api.repositories import catalog_repository
from read_api.server.deps import session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(s: Session = Depends(session)):
    w = catalog_repository.world(s)
    return {"service": "read_api", "ok": True, "db": "read-only", "world_loaded": w.fixture_id if w else None}
