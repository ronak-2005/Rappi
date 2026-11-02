"""INSERT supplier availability limits (a supplier said it can't supply more for a while)."""

from datetime import date, timedelta

from sqlmodel import Session

from shared.db import models as m


def record_unavailable(
    session: Session, supplier_id: str, sku_id: str, today: date, days: int, note: str, available_qty: int = 0
) -> m.SupplierAvailability:
    row = m.SupplierAvailability(
        supplier_id=supplier_id,
        sku_id=sku_id,
        available_qty=available_qty,
        until=today + timedelta(days=days),
        note=note[:300],
    )
    session.add(row)
    session.commit()
    return row
