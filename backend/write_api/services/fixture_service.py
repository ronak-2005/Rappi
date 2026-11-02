"""Use-case: load a scenario world (fixture) into the database, replacing whatever was there."""

from shared.db.session import read_write
from shared.domain.fixtures import FixtureSpec, load_fixture_file
from write_api.repositories import world_repository


def load_world(fixture_id: str, db_file: str | None = None) -> FixtureSpec:
    fx = load_fixture_file(fixture_id)
    with read_write(db_file) as session:
        world_repository.reset_database(session)
        world_repository.insert_world(session, fx)
    return fx
