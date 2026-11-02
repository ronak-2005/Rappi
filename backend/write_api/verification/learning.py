"""Feedback loop #3: every supplier answer updates that supplier's fill-rate and on-time statistics,
so the next decision (and the supplier_reliability rule) sees the supplier's real behaviour."""

from sqlmodel import Session

from shared.domain.decision import ExecutionResult
from write_api.repositories import supplier_repository


def record(session: Session, execution: ExecutionResult) -> list[dict]:
    updates = []
    for ln in execution.lines:
        if ln.supplier_id.startswith("transfer:") or ln.status == "failed" or ln.replayed and ln.attempts == 0:
            continue  # no real answer, or a line we already learned from
        ratio = ln.qty_confirmed / ln.qty_requested if ln.qty_requested else 1.0
        on_time = ln.confirmed_delivery is None or ln.confirmed_delivery <= ln.requested_delivery
        s = supplier_repository.update_stats(session, ln.supplier_id, ratio, on_time)
        if s:
            updates.append({"supplier": s.id, "fill_rate": s.fill_rate, "on_time_rate": s.on_time_rate,
                            "orders_observed": s.orders_observed})
    return updates
