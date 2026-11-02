"""Human approval requests: created when a plan breaks a soft rule, resolved by a person in the UI."""

from sqlmodel import Session

from shared.domain.errors import ConflictError, NotFoundError
from write_api.repositories import run_repository as runs


def request(session: Session, run_id: str, reasons: list[str], plan: dict):
    n = len(runs.steps(session, run_id))
    return runs.create_approval(session, f"APR-{run_id[-6:]}-{n}", run_id, reasons, plan)


def resolve(session: Session, approval_id: str, decision: str, by: str, comment: str = "", edited_lines=None):
    a = runs.get_approval(session, approval_id)
    if a is None:
        raise NotFoundError("approval", approval_id, "write_api.actions.approvals")
    if a.status != "pending":
        raise ConflictError(f"approval {approval_id} is already {a.status}", "write_api.actions.approvals")
    status = {"approve": "approved", "reject": "rejected", "edit": "edited"}[decision]
    if edited_lines is not None:
        a.plan = {**a.plan, "lines": edited_lines}
    return runs.resolve_approval(session, a, status, by, comment)
