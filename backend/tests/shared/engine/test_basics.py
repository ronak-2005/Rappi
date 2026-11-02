"""Unit tests for the small engine pieces (calendar, safety stock, rounding, projection)."""

from datetime import date

from shared.domain.planning import Receipt
from shared.engine.calendar import arrival_day
from shared.engine.projection import project
from shared.engine.requirement import net_requirement, round_down_to_pack, round_to_pack
from shared.engine.safety_stock import safety_stock

MONDAY = date(2026, 11, 2)


def test_arrival_respects_cutoff_and_weekdays():
    assert arrival_day(MONDAY, 10, 3, 14, list(range(7))) == 3            # before cut-off
    assert arrival_day(MONDAY, 15, 3, 14, list(range(7))) == 4            # after cut-off → +1
    assert arrival_day(MONDAY, 10, 3, 14, [1, 4]) == 4                    # Thu (day 3) not allowed → Fri


def test_safety_stock_matches_hand_calc():
    assert safety_stock(1.65, [30] * 10, 100) == 157   # 1.65 × 30 × √10 = 156.5
    assert safety_stock(1.65, [12] * 9, 40) == 60      # 1.65 × 12 × 3 = 59.4
    assert safety_stock(1.65, [40] * 9, 150) == 198    # 1.65 × 40 × 3 = 198.0
    assert safety_stock(1.65, [0] * 9, 100, lead_time_sigma_days=1) == 165  # lead-time variability only


def test_rounding():
    assert round_to_pack(457, 500, 20) == 500
    assert round_to_pack(757, 500, 20) == 760
    assert round_to_pack(0, 500, 20) == 0
    assert round_to_pack(-10, 500, 20) == 0
    assert round_down_to_pack(500 / 1.2, 20) == 400


def test_requirement_counts_open_po_only_inside_horizon():
    late = Receipt(day=12, qty=999, source="late")
    early = Receipt(day=2, qty=400, source="PO-1001")
    r = net_requirement(on_hand=300, demand=[100] * 30, sigmas=[30] * 30, open_receipts=[early, late],
                        arrival_day=3, review_period_days=7, z=1.65, moq=500, case_pack=20)
    assert r.horizon_days == 10 and r.demand_over_horizon == 1000 and r.safety_stock == 157
    assert r.open_receipts_in_horizon == 400 and r.open_receipts_after_horizon == 999
    assert r.net_requirement == 457 and r.order_qty == 500


def test_projection_fefo_expiry_and_capacity():
    p = project(on_hand=100, on_hand_remaining_shelf_life_days=3, demand=[10] * 10,
                receipts=[Receipt(day=1, qty=50, remaining_shelf_life_days=20, source="x", is_new=True)],
                unit_volume_l=1.0, zone_free_l=[120] * 10, safety_stock=0, horizon_days=10)
    # old lot written off at start of day 2 (0 + 3 − 1): 100 − 20 sold = 80 expire
    assert p.days[2].expired == 80
    assert p.expired_units_new == 0
    assert p.over_capacity_days == [1]  # day 1: 90 old + 50 new = 140 L > 120 L
    assert p.lost_units == 30  # only the 50 new units remain after the write-off → days 7–9 short


def test_projection_counts_lost_sales_not_backorders():
    p = project(on_hand=50, on_hand_remaining_shelf_life_days=None, demand=[100] * 3, receipts=[],
                unit_volume_l=1, zone_free_l=[1000] * 3, safety_stock=0, horizon_days=3)
    assert [d.lost for d in p.days] == [50, 100, 100]
    assert p.first_stockout_day == 0
