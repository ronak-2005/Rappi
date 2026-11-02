"""How the fake supplier answers a purchase order. Configured per scenario via POST /admin/scenario.

Modes: confirm · partial (ratio) · reject · delay (days) · price_change · timeout_once
`apply_to: first` → only the first order to that supplier misbehaves, later ones are confirmed.
timeout_once stores the order and then answers 504, like a real API whose response got lost;
a retry with the same idempotency key gets the stored confirmation.
"""

import math
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel


class Behaviour(BaseModel):
    mode: Literal["confirm", "partial", "reject", "delay", "timeout_once", "price_change"] = "confirm"
    ratio: float = 1.0
    delay_days: int = 0
    new_unit_cost: float | None = None
    apply_to: Literal["first", "all"] = "all"


class OrderIn(BaseModel):
    idempotency_key: str
    po_id: str
    supplier_id: str
    sku_id: str
    qty: int
    unit_cost: float
    requested_delivery: date
    mode: str = "standard"


class OrderOut(BaseModel):
    supplier_order_id: str
    po_id: str
    status: Literal["confirmed", "partially_confirmed", "rejected"]
    qty_confirmed: int
    delivery_date: date
    unit_cost: float
    message: str


def respond(order: OrderIn, behaviour: Behaviour, order_number: int) -> tuple[OrderOut, bool]:
    """Returns (response, simulate_timeout). order_number = how many orders this supplier got before."""
    b = behaviour if (behaviour.apply_to == "all" or order_number == 0) else Behaviour()
    sid = f"{order.supplier_id}-{order_number + 1:04d}"
    out = OrderOut(
        supplier_order_id=sid,
        po_id=order.po_id,
        status="confirmed",
        qty_confirmed=order.qty,
        delivery_date=order.requested_delivery,
        unit_cost=order.unit_cost,
        message="Confirmed in full.",
    )
    if b.mode == "partial":
        qty = math.floor(order.qty * b.ratio)
        out.status, out.qty_confirmed = "partially_confirmed", qty
        out.message = f"We can only supply {qty} of {order.qty} units at the moment; the rest is not available."
    elif b.mode == "reject":
        out.status, out.qty_confirmed = "rejected", 0
        out.message = "Order rejected: product unavailable."
    elif b.mode == "delay":
        out.delivery_date = order.requested_delivery + timedelta(days=b.delay_days)
        out.message = f"Confirmed, but delivery moves {b.delay_days} day(s) later."
    elif b.mode == "price_change" and b.new_unit_cost is not None:
        out.unit_cost = b.new_unit_cost
        out.message = f"Confirmed at a new unit price of {b.new_unit_cost}."
    return out, b.mode == "timeout_once"
