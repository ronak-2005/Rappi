"""SOFT: the agent may plan on a demand different from the forecast, but if it assumes MORE than the
sales evidence supports (the forecast or the recent level, measured over 7 or 3 days, +10%), a human must
sign off. This stops an
agent from inflating demand to justify buying more."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput

TOLERANCE = 1.10


def check(i: RuleInput) -> RuleResult:
    if i.demand is None:
        return RuleResult(rule="forecast_override", kind="soft", passed=True, message="plan uses the forecast")
    sig = i.demand_signal
    supported = max(sig.forecast_per_day, sig.recent_7d_avg or 0, sig.recent_3d_avg or 0) if sig else 0
    ok = i.demand.per_day <= supported * TOLERANCE
    return RuleResult(
        rule="forecast_override",
        kind="soft",
        passed=ok,
        message=f"assumes {i.demand.per_day:g}/day; evidence supports up to {supported:g}/day "
        f"(forecast {sig.forecast_per_day if sig else '?'}, recent 7-day {sig.recent_7d_avg if sig else '?'}, "
        f"3-day {sig.recent_3d_avg if sig else '?'})",
    )
