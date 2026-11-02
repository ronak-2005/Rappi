"""Safety stock for a periodic-review (order-up-to) policy.

SS = z × √( Σσ_d² over the protection interval  +  d̄² × σ_L² )

- protection interval = arrival offset (lead time) + review period
- first term: demand uncertainty; second: lead-time uncertainty
Reference: Silver, Pyke & Thomas, *Inventory and Production Management in Supply Chains* (periodic review).
"""

import math


def safety_stock(
    z: float, daily_sigmas: list[float], mean_daily_demand: float, lead_time_sigma_days: float = 0.0
) -> float:
    variance = sum(s * s for s in daily_sigmas) + (mean_daily_demand**2) * (lead_time_sigma_days**2)
    return math.ceil(z * math.sqrt(variance) - 1e-9) if variance > 0 else 0.0
