"""Run a fixture end-to-end in-process: read_api, write side (orchestrator) and mock supplier talk
over real HTTP semantics via TestClient, with no ports and a throw-away database."""

from dataclasses import dataclass

from fastapi.testclient import TestClient
from sqlmodel import select

from mock_supplier.server.main import create_app as create_supplier
from read_api.server.main import create_app as create_read
from shared.config.llm_settings import LLMSettings
from shared.db import models as m
from shared.db.session import read_write
from shared.domain.fixtures import FixtureSpec, load_fixture_file
from write_api.agent.orchestrator import Orchestrator
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.llm.client import LLMClient
from write_api.services import fixture_service, run_service


@dataclass
class RunRecord:
    fixture: FixtureSpec
    run: dict
    steps: list[dict]
    agent_pos: list[dict]
    supplier_orders: list[dict]
    approvals_requested: int
    error: str | None = None


def run_fixture(
    fixture_id: str, db_file: str, *, llm_settings: LLMSettings | None = None, llm: LLMClient | None = None
) -> RunRecord:
    fx = load_fixture_file(fixture_id)
    read = ReadApiClient(TestClient(create_read(db_file)))
    supplier = SupplierClient(TestClient(create_supplier()))
    fixture_service.load_world(fixture_id, db_file, supplier)
    asked = []

    def approver(approval: dict):
        asked.append(approval)
        return fx.expected.approval_response, "eval auto-approver", None

    deps = run_service.make_deps(
        db_file=db_file,
        read=read,
        supplier=supplier,
        llm_settings=llm_settings or LLMSettings(llm_mode="baseline"),
        approver=approver,
    )
    if llm is not None:
        deps.llm = llm
    orch = Orchestrator(deps)
    run_id = orch.start(fx.trigger.ref, fx.trigger.type)
    orch.run(run_id)
    with read_write(db_file) as s:
        run = s.get(m.AgentRun, run_id).model_dump()
        steps = [
            x.model_dump()
            for x in s.exec(select(m.TraceStep).where(m.TraceStep.run_id == run_id).order_by(m.TraceStep.seq)).all()
        ]
        pos = [
            p.model_dump() for p in s.exec(select(m.PurchaseOrder).where(m.PurchaseOrder.created_by == "agent")).all()
        ]
    return RunRecord(
        fixture=fx,
        run=run,
        steps=steps,
        agent_pos=pos,
        supplier_orders=supplier.orders(),
        approvals_requested=len(asked),
        error=run.get("error"),
    )
