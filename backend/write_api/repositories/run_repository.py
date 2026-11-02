"""INSERT/UPDATE for agent runs, trace steps and approvals."""

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, func, select

from shared.db import models as m


def now() -> datetime:
    return datetime.now(timezone.utc)


def create_run(session: Session, **fields) -> m.AgentRun:
    run = m.AgentRun(started_at=now(), **fields)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def get_run(session: Session, run_id: str) -> m.AgentRun | None:
    return session.get(m.AgentRun, run_id)


def update_run(session: Session, run: m.AgentRun, **fields) -> m.AgentRun:
    for k, v in fields.items():
        setattr(run, k, v)
    session.add(run)
    session.commit()
    session.refresh(run)
    return run


def add_step(session: Session, run_id: str, state: str, kind: str, name: str, payload: dict[str, Any]) -> m.TraceStep:
    seq = session.exec(select(func.coalesce(func.max(m.TraceStep.seq), -1)).where(m.TraceStep.run_id == run_id)).one() + 1
    step = m.TraceStep(run_id=run_id, seq=seq, at=now(), state=state, kind=kind, name=name, payload=payload)
    session.add(step)
    session.commit()
    session.refresh(step)
    return step


def steps(session: Session, run_id: str) -> list[m.TraceStep]:
    return list(session.exec(select(m.TraceStep).where(m.TraceStep.run_id == run_id).order_by(m.TraceStep.seq)).all())


def create_approval(session: Session, approval_id: str, run_id: str, reasons: list[str], plan: dict) -> m.Approval:
    a = m.Approval(id=approval_id, run_id=run_id, reasons=reasons, plan=plan, created_at=now())
    session.add(a)
    session.commit()
    session.refresh(a)
    return a


def get_approval(session: Session, approval_id: str) -> m.Approval | None:
    return session.get(m.Approval, approval_id)


def pending_approval_for_run(session: Session, run_id: str) -> m.Approval | None:
    return session.exec(select(m.Approval).where(m.Approval.run_id == run_id, m.Approval.status == "pending")).first()


def resolve_approval(session: Session, a: m.Approval, status: str, by: str, comment: str) -> m.Approval:
    a.status, a.resolved_by, a.comment, a.resolved_at = status, by, comment, now()
    session.add(a)
    session.commit()
    session.refresh(a)
    return a
