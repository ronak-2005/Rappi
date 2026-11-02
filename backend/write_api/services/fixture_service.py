"""Use-case: load a scenario world (fixture) into the database, replacing whatever was there,
and tell the mock supplier how to behave for this scenario."""

from shared.db.session import read_write
from shared.domain.fixtures import FixtureSpec, load_fixture_file
from write_api.clients.supplier_client import SupplierClient
from write_api.repositories import world_repository
from write_api.services import supplier_event_service


def load_world(fixture_id: str, db_file: str | None = None, supplier: SupplierClient | None = None) -> FixtureSpec:
    fx = load_fixture_file(fixture_id)
    with read_write(db_file) as session:
        world_repository.reset_database(session)
        world_repository.insert_world(session, fx)
        if fx.trigger.supplier_event:  # the supplier's message "arrives" when the world is loaded
            supplier_event_service.apply(
                session, fx.trigger.supplier_event.id, fx.trigger.supplier_event.unavailable_days
            )
    if supplier is not None:
        supplier.set_scenario({k: v.model_dump() for k, v in fx.supplier_behaviour.items()})
    return fx
