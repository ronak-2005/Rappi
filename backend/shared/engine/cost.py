"""Decision cost: only the costs that DIFFER between options, so options can be compared fairly.

Purchase cost itself is not a 'cost' here (the goods get sold); what differs is:
  price_premium   paying more per unit than the cheapest supplier
  express         express delivery premium
  holding         carrying stock (close of each horizon day × unit cost × daily %)
  stockout        avoidable lost sales × unit margin × churn multiplier (quick-commerce customers leave)
  waste           units of this plan that expire × their unit cost
  transfer        moving stock from another dark store (handling cost per unit)
Purchase cost is still reported separately because the budget rule needs it.
"""


def decision_cost(
    *,
    line_costs: list[tuple[int, float]],  # (qty, unit_cost incl. nothing) per line
    express_premium: float,
    reference_unit_cost: float,
    horizon_closes: list[float],
    holding_pct_per_day: float,
    avoidable_lost_units: float,
    unit_margin: float,
    stockout_multiplier: float,
    expired_units_new: float,
    transfer_cost: float = 0.0,
) -> tuple[float, dict[str, float]]:
    qty = sum(q for q, _ in line_costs)
    avg_cost = (sum(q * c for q, c in line_costs) / qty) if qty else reference_unit_cost
    breakdown = {
        "price_premium": sum(q * (c - reference_unit_cost) for q, c in line_costs),
        "express": express_premium,
        "holding": sum(max(0.0, c) for c in horizon_closes) * reference_unit_cost * holding_pct_per_day / 100,
        "stockout": avoidable_lost_units * unit_margin * stockout_multiplier,
        "waste": expired_units_new * avg_cost,
        "transfer": transfer_cost,
    }
    breakdown = {k: round(v, 2) for k, v in breakdown.items()}
    return round(sum(breakdown.values()), 2), breakdown
