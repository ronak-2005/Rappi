"""Data sanity checks raise the right flags with evidence."""

from shared.engine.data_quality import check

SALES = [(d, 100, False) for d in range(1, 15)]


def codes(**kw):
    base = dict(on_hand=300, last_counted_days_ago=1, sales=SALES, receipts_last_days=0,
                forecast_next_7_avg=100, stale_count_days=7, forecast_vs_sales_ratio_max=1.5)
    base.update(kw)
    return {a.code for a in check(**base)}


def test_clean_data_has_no_flags():
    assert codes() == set()


def test_phantom_stock_fixture_pattern():
    assert codes(on_hand=0, last_counted_days_ago=21) == {"sales_while_zero_stock", "stale_count"}


def test_zero_stock_is_fine_if_it_really_ran_out():
    sales = [(1, 0, True), (2, 0, True)] + [(d, 100, False) for d in range(3, 15)]
    assert "sales_while_zero_stock" not in codes(on_hand=0, sales=sales)
    assert "censored_demand" in codes(on_hand=0, sales=sales)


def test_negative_stock_and_forecast_mismatch():
    assert "negative_stock" in codes(on_hand=-5)
    assert "forecast_mismatch" in codes(forecast_next_7_avg=180)
