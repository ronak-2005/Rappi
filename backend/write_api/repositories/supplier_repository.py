"""UPDATE supplier performance statistics (the learning loop)."""

from sqlmodel import Session

from shared.db import models as m


def update_stats(session: Session, supplier_id: str, fill_ratio: float, on_time: bool) -> m.Supplier | None:
    s = session.get(m.Supplier, supplier_id)
    if s is None:
        return None
    n = s.orders_observed
    s.fill_rate = round((s.fill_rate * n + fill_ratio) / (n + 1), 4)
    s.on_time_rate = round((s.on_time_rate * n + (1.0 if on_time else 0.0)) / (n + 1), 4)
    s.orders_observed = n + 1
    session.add(s)
    session.commit()
    session.refresh(s)
    return s
