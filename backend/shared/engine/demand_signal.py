"""Demand signal (Scenario 3): what recent sales say compared with the forecast.

Facts first (averages, how many days were elevated, whether a promotion covers them, stockout days),
then a classification and a suggested demand assumption. The agent decides; the engine only measures.

  promotion           most elevated days fall inside a promotion → uplift only until the promotion ends
  sustained_increase  ≥ 5 of the last 7 days elevated, no promotion → recent level for the whole horizon
  one_off_spike       ≤ 2 elevated days, including yesterday → noise (e.g. a bulk order): keep the forecast
  censored_drop       sales below forecast but with stockout days → demand was hidden: keep the forecast
  sustained_decrease  sales well below forecast without stockouts → recent level
  normal              nothing unusual
"""

from typing import Optional

from shared.domain.planning import DemandAssumption, DemandSignal

ELEVATED = 1.25  # a day is "elevated" if sales > 25% above the forecast level


def analyze(*, forecast_per_day: float, sales: list[tuple[int, int, bool]],
            promotions: list[dict]) -> DemandSignal:
    """sales: (days_ago, units, stocked_out). promotions: {start_offset, end_offset, uplift_pct, description}
    with offsets relative to today (negative = past)."""
    by_ago = {d: (u, out) for d, u, out in sales}
    last7 = [(d, *by_ago[d]) for d in range(1, 8) if d in by_ago]
    clean7 = [u for _, u, out in last7 if not out]
    clean3 = [u for d, u, out in last7 if d <= 3 and not out]
    avg7 = sum(clean7) / len(clean7) if clean7 else None
    avg3 = sum(clean3) / len(clean3) if clean3 else None
    yesterday = by_ago.get(1, (None, False))[0]
    stockouts = sum(1 for _, _, out in last7 if out)

    elevated = [d for d, u, out in last7 if not out and u > ELEVATED * forecast_per_day]
    in_promo = lambda d: next((p for p in promotions if p["start_offset"] <= -d <= p["end_offset"]), None)  # noqa: E731
    explained = [d for d in elevated if in_promo(d)]
    promo = in_promo(elevated[0]) if explained else next((p for p in promotions if p["end_offset"] >= 0), None)
    ratio = round(avg7 / forecast_per_day, 2) if avg7 and forecast_per_day else None

    suggestion: Optional[DemandAssumption] = None
    if len(elevated) >= 3 and len(explained) >= 0.8 * len(elevated):
        cls = "promotion"
        end = promo["end_offset"]
        promo_level = sum(by_ago[d][0] for d in explained) / len(explained)
        if end >= 0:
            suggestion = DemandAssumption(per_day=round(promo_level, 1), until_day=end + 1,
                                          reason=f"promotion uplift until it ends (day {end}), then the forecast")
        text = (f"{len(elevated)} of the last 7 days were elevated and {len(explained)} of them fall inside the promotion "
                f"'{promo.get('description', '')}' ending {'today' if end == 0 else f'in {end} day(s)' if end > 0 else f'{-end} day(s) ago'}. "
                "The increase is temporary.")
    elif len(elevated) >= 5:
        cls = "sustained_increase"
        suggestion = DemandAssumption(per_day=round(avg7, 1), reason="sales above forecast on most of the last 7 days")
        text = f"Sales were above forecast on {len(elevated)} of the last 7 days (avg {avg7:.0f} vs {forecast_per_day:.0f}), with no promotion: a real level change."
    elif elevated and len(elevated) <= 2 and 1 in elevated:
        cls = "one_off_spike"
        text = (f"Only {len(elevated)} elevated day(s) (yesterday: {yesterday}); the rest of the week matches the "
                "forecast. Looks like a one-off (e.g. a bulk order): keep the forecast.")
    elif ratio is not None and ratio < 0.75 and stockouts >= 2:
        cls = "censored_drop"
        text = f"Sales fell below forecast, but the shelf was empty on {stockouts} of the last 7 days: demand was hidden, not lower."
    elif ratio is not None and ratio < 0.75:
        cls = "sustained_decrease"
        suggestion = DemandAssumption(per_day=round(avg7, 1), reason="sales well below forecast without stockouts")
        text = f"Sales averaged {avg7:.0f} vs forecast {forecast_per_day:.0f} without stockouts."
    else:
        cls = "normal"
        text = "Recent sales are consistent with the forecast."

    return DemandSignal(
        forecast_per_day=round(forecast_per_day, 1), recent_7d_avg=round(avg7, 1) if avg7 else None,
        recent_3d_avg=round(avg3, 1) if avg3 else None, yesterday=yesterday, ratio_7d=ratio,
        elevated_days_last_7=len(elevated), elevated_days_explained_by_promotion=len(explained),
        stockout_days_last_7=stockouts, promotion=promo, classification=cls, explanation=text,
        suggested_assumption=suggestion,
    )


def apply_assumption(demand: list[float], assumption: Optional[DemandAssumption]) -> list[float]:
    if assumption is None:
        return list(demand)
    end = len(demand) if assumption.until_day is None else min(assumption.until_day, len(demand))
    return [assumption.per_day if i < end else d for i, d in enumerate(demand)]
