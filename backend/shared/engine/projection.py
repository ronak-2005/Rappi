"""Day-by-day stock projection with FEFO lots, shelf-life write-offs and storage checks.

Each day, in order:
  1. receipts arriving that day are added as lots
  2. lots past their write-off day are removed (expired)
  3. peak stock (available) is checked against free storage
  4. demand is served first-expiring-first (FEFO); unmet demand is lost (quick-commerce: no backorders)

Shelf-life convention: a lot arriving on day a with r days left is written off at the start of
day a + r − buffer (buffer = days before expiry we stop selling).
"""

from dataclasses import dataclass

from shared.domain.planning import Projection, ProjectionDay, Receipt


@dataclass
class _Lot:
    qty: float
    writeoff_day: int | None
    is_new: bool


def project(
    *,
    on_hand: float,
    on_hand_remaining_shelf_life_days: int | None,
    demand: list[float],
    receipts: list[Receipt],
    unit_volume_l: float,
    zone_free_l: list[float],
    safety_stock: float,
    horizon_days: int,
    sell_buffer_days: int = 1,
    check_ss_from_day: int = 0,
) -> Projection:
    """Simulate len(demand) days. Stockout and safety-stock metrics count only days < horizon_days;
    expiry is tracked over the whole simulation (a lot can expire after the horizon)."""
    sim_days = len(demand)
    lots: list[_Lot] = []
    if on_hand > 0:
        wo = None if on_hand_remaining_shelf_life_days is None else on_hand_remaining_shelf_life_days - sell_buffer_days
        lots.append(_Lot(on_hand, wo, False))

    by_day: dict[int, list[Receipt]] = {}
    for r in receipts:
        by_day.setdefault(r.day, []).append(r)

    days: list[ProjectionDay] = []
    close = float(on_hand)
    expired_new = expired_total = 0.0
    for d in range(sim_days):
        open_ = close
        received = 0.0
        for r in by_day.get(d, []):
            wo = None if r.remaining_shelf_life_days is None else d + r.remaining_shelf_life_days - sell_buffer_days
            lots.append(_Lot(r.qty, wo, r.is_new))
            received += r.qty

        expired = 0.0
        for lot in lots:
            if lot.writeoff_day is not None and lot.writeoff_day <= d and lot.qty > 0:
                expired += lot.qty
                if lot.is_new:
                    expired_new += lot.qty
                lot.qty = 0
        expired_total += expired
        lots = [lot for lot in lots if lot.qty > 0]

        available = sum(lot.qty for lot in lots)
        free = zone_free_l[d] if d < len(zone_free_l) else zone_free_l[-1]
        volume = available * unit_volume_l

        remaining = demand[d]
        lots.sort(key=lambda lot: (lot.writeoff_day is None, lot.writeoff_day if lot.writeoff_day is not None else 0))
        for lot in lots:
            take = min(lot.qty, remaining)
            lot.qty -= take
            remaining -= take
            if remaining <= 0:
                break
        lots = [lot for lot in lots if lot.qty > 0]
        sold = demand[d] - remaining
        close = available - sold

        days.append(
            ProjectionDay(
                day=d,
                open=round(open_, 2),
                receipts=round(received, 2),
                expired=round(expired, 2),
                available=round(available, 2),
                demand=round(demand[d], 2),
                sold=round(sold, 2),
                lost=round(remaining, 2),
                close=round(close, 2),
                volume_l=round(volume, 2),
                free_l=round(free, 2),
                over_capacity=volume > free + 1e-6,
                below_ss=d < horizon_days and d >= check_ss_from_day and close < safety_stock - 1e-6,
            )
        )

    in_h = [x for x in days if x.day < horizon_days]
    stockouts = [x.day for x in in_h if x.lost > 1e-6]
    return Projection(
        horizon_days=horizon_days,
        safety_stock=safety_stock,
        days=days,
        lost_units=round(sum(x.lost for x in in_h), 2),
        first_stockout_day=stockouts[0] if stockouts else None,
        expired_units_new=round(expired_new, 2),
        expired_units_total=round(expired_total, 2),
        over_capacity_days=[x.day for x in days if x.over_capacity],
        below_ss_days=[x.day for x in in_h if x.below_ss],
        min_close=min((x.close for x in in_h if x.day >= check_ss_from_day), default=close),
        end_close=in_h[-1].close if in_h else close,
    )
