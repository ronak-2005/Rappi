"""Net requirement for one SKU at one node, with every term exposed for explanation.

need = demand over (arrival + review period) + safety stock − (on hand + open receipts inside that window)
order qty = need rounded up to the case pack, and at least the MOQ (0 if need ≤ 0)

Open receipts are counted on their real arrival day: a PO landing after the horizon does not
protect this cycle (it is reported separately).
"""

import math

from shared.domain.planning import Receipt, Requirement
from shared.engine.safety_stock import safety_stock


def round_to_pack(qty: float, moq: int, case_pack: int) -> int:
    if qty <= 0:
        return 0
    packs = math.ceil(qty / case_pack - 1e-9)
    return max(moq, packs * case_pack)


def round_down_to_pack(qty: float, case_pack: int) -> int:
    return max(0, math.floor(qty / case_pack + 1e-9) * case_pack)


def net_requirement(
    *,
    on_hand: float,
    demand: list[float],
    sigmas: list[float],
    open_receipts: list[Receipt],
    arrival_day: int,
    review_period_days: int,
    z: float,
    lead_time_sigma_days: float = 0.0,
    moq: int = 1,
    case_pack: int = 1,
) -> Requirement:
    horizon = arrival_day + review_period_days
    window = demand[:horizon]
    demand_h = sum(window)
    mean = demand_h / horizon if horizon else 0.0
    ss = safety_stock(z, sigmas[:horizon], mean, lead_time_sigma_days)
    inside = sum(r.qty for r in open_receipts if r.day < horizon)
    after = sum(r.qty for r in open_receipts if r.day >= horizon)
    position = on_hand + inside
    need = demand_h + ss - position
    return Requirement(
        arrival_day=arrival_day,
        review_period_days=review_period_days,
        horizon_days=horizon,
        demand_over_horizon=round(demand_h, 2),
        safety_stock=ss,
        on_hand=on_hand,
        open_receipts_in_horizon=inside,
        open_receipts_after_horizon=after,
        inventory_position=position,
        net_requirement=round(need, 2),
        order_qty=round_to_pack(need, moq, case_pack),
        moq=moq,
        case_pack=case_pack,
    )
