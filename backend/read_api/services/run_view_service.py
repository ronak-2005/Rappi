"""Read-side views of agent runs: list, detail (decision, outcome, POs, approvals) and trace."""

from sqlmodel import Session

from read_api.repositories import order_repository as orders
from read_api.repositories import run_repository as runs
from shared.domain.errors import NotFoundError

FINISHED = ("completed", "escalated", "failed", "cancelled")


def list_runs(session: Session) -> list[dict]:
    return [{"id": r.id, "fixture_id": r.fixture_id, "status": r.status, "state": r.state, "llm_mode": r.llm_mode,
             "llm_model": r.llm_model, "started_at": r.started_at, "finished_at": r.finished_at,
             "decision_type": (r.decision or {}).get("type")} for r in runs.runs(session)]


def run_detail(session: Session, run_id: str) -> dict:
    r = runs.run(session, run_id)
    if r is None:
        raise NotFoundError("run", run_id)
    data = r.model_dump(exclude={"memory"})  # the full LLM conversation stays out of this hot path
    mem = r.memory or {}
    return {
        **data,
        "context": {"node": mem.get("node"), "sku": mem.get("sku"), "recommendation_id": mem.get("recommendation_id")},
        "finished": r.status in FINISHED,
        "purchase_orders": [{**p.model_dump(), "events": [e.model_dump() for e in orders.po_events(session, p.id)]}
                            for p in orders.purchase_orders(session, run_id=run_id)],
        "transfers": [t.model_dump() for t in orders.transfers(session, run_id=run_id)],
        "approvals": [a.model_dump() for a in runs.approvals(session, run_id=run_id)],
    }


def trace(session: Session, run_id: str, after_seq: int = -1) -> list[dict]:
    return [s.model_dump() for s in runs.trace(session, run_id, after_seq)]


def approvals(session: Session, status: str | None) -> list[dict]:
    return [a.model_dump() for a in runs.approvals(session, status=status)]


def purchase_orders(session: Session) -> list[dict]:
    return [{**p.model_dump(), "events": [e.model_dump() for e in orders.po_events(session, p.id)]}
            for p in orders.purchase_orders(session)]
