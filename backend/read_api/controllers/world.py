"""GET: the loaded scenario world and the catalogue of fixture scenarios."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from read_api.server.deps import session
from read_api.services import facts_service
from shared.domain.errors import NotFoundError
from shared.domain.fixtures import list_fixture_files, load_fixture_file

router = APIRouter(tags=["world"])


@router.get("/world")
def get_world(s: Session = Depends(session)):
    return facts_service.world(s)


@router.get("/fixtures")
def list_fixtures():
    return [
        {
            "id": f.id,
            "scenario": f.scenario,
            "title": f.title,
            "description": f.description,
            "trigger": f.trigger.model_dump(),
            "expected": f.expected.model_dump(),
        }
        for f in list_fixture_files()
    ]


@router.get("/fixtures/{fixture_id}")
def get_fixture(fixture_id: str):
    try:
        return load_fixture_file(fixture_id).model_dump()
    except FileNotFoundError as exc:
        raise NotFoundError("fixture", fixture_id, "read_api.controllers.world") from exc
