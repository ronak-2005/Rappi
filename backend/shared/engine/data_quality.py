"""Data sanity checks: flag facts that don't add up before anyone buys on top of them.

The engine only raises flags with evidence; the agent decides what they mean (usually: investigate).
"""

from shared.domain.planning import Anomaly


def check(
    *,
    on_hand: float,
    last_counted_days_ago: int,
    sales: list[tuple[int, int, bool]],  # (days_ago, units, stocked_out), any order
    receipts_last_days: float,  # units received since the last count
    forecast_next_7_avg: float,
    stale_count_days: int,
    forecast_vs_sales_ratio_max: float,
) -> list[Anomaly]:
    out: list[Anomaly] = []
    recent = sorted(sales)  # days_ago ascending: yesterday first

    if on_hand < 0:
        out.append(
            Anomaly(
                code="negative_stock",
                severity="high",
                message=f"Stock record is negative ({on_hand}); the count is wrong.",
                evidence={"on_hand": on_hand},
            )
        )

    sold_since_count = sum(u for d, u, _ in recent if d <= last_counted_days_ago)
    if on_hand <= 0 and receipts_last_days == 0:
        # Only yesterday matters: a store that genuinely sold out a few days ago is consistent with 0.
        yesterday = next(((u, out_) for d, u, out_ in recent if d == 1), None)
        if yesterday and yesterday[0] > 0 and not yesterday[1]:
            out.append(
                Anomaly(
                    code="sales_while_zero_stock",
                    severity="high",
                    message=(
                        f"System shows {on_hand:g} units and nothing was received, yet {yesterday[0]} units "
                        "sold yesterday without a stockout. The stock record is wrong."
                    ),
                    evidence={
                        "on_hand": on_hand,
                        "sold_yesterday": yesterday[0],
                        "receipts_since_count": receipts_last_days,
                    },
                )
            )

    if last_counted_days_ago > stale_count_days:
        out.append(
            Anomaly(
                code="stale_count",
                severity="medium",
                message=f"Stock was last counted {last_counted_days_ago} days ago (limit {stale_count_days}).",
                evidence={"last_counted_days_ago": last_counted_days_ago, "sold_since_count": sold_since_count},
            )
        )

    stockout_days = [d for d, _, out_ in recent if out_]
    if stockout_days:
        out.append(
            Anomaly(
                code="censored_demand",
                severity="medium",
                message=(
                    f"Out of stock on {len(stockout_days)} of the last {len(recent)} days: sales on those days "
                    "understate real demand."
                ),
                evidence={"stockout_days_ago": stockout_days},
            )
        )

    clean7 = [u for d, u, out_ in recent if d <= 7 and not out_]
    if clean7 and forecast_next_7_avg > 0:
        actual = sum(clean7) / len(clean7)
        ratio = forecast_next_7_avg / actual if actual else float("inf")
        if ratio > forecast_vs_sales_ratio_max or ratio < 1 / forecast_vs_sales_ratio_max:
            out.append(
                Anomaly(
                    code="forecast_mismatch",
                    severity="medium",
                    message=(
                        f"Forecast ({forecast_next_7_avg:.0f}/day) differs from recent sales "
                        f"({actual:.0f}/day) by ×{ratio:.2f}."
                    ),
                    evidence={
                        "forecast_avg": round(forecast_next_7_avg, 1),
                        "sales_avg_7d": round(actual, 1),
                        "ratio": round(ratio, 2),
                    },
                )
            )
    return out
