"""FastAPI dependencies for the read side: a READ-ONLY session and the business policy."""

from collections.abc import Iterator

from fastapi import Request
from sqlmodel import Session

from shared.config.policy import Policy, get_policy
from shared.db.session import read_only


def session(request: Request) -> Iterator[Session]:
    with read_only(request.app.state.db_file) as s:
        yield s


def policy() -> Policy:
    return get_policy()
