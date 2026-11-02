"""SELECT-only access to agent runs, their trace steps and approvals."""

from sqlmodel import Session, select

from shared.db import models as m


def runs(session: Session, limit: int = 50) -> list[m.AgentRun]:
    return list(session.exec(select(m.AgentRun).order_by(m.AgentRun.started_at.desc()).limit(limit)).all())


def run(session: Session, run_id: str) -> m.AgentRun | None:
    return session.get(m.AgentRun, run_id)


def trace(session: Session, run_id: str, after_seq: int = -1) -> list[m.TraceStep]:
    return list(session.exec(select(m.TraceStep).where(
        m.TraceStep.run_id == run_id, m.TraceStep.seq > after_seq).order_by(m.TraceStep.seq)).all())


def approvals(session: Session, status: str | None = None, run_id: str | None = None) -> list[m.Approval]:
    q = select(m.Approval)
    if status:
        q = q.where(m.Approval.status == status)
    if run_id:
        q = q.where(m.Approval.run_id == run_id)
    return list(session.exec(q.order_by(m.Approval.created_at.desc())).all())
