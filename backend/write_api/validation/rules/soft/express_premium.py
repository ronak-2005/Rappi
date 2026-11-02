"""SOFT: express delivery premiums above the threshold need a human."""

from shared.domain.decision import RuleResult
from write_api.validation.rules.base import RuleInput


def check(i: RuleInput) -> RuleResult:
    p, limit = i.evaluation.express_premium, i.policy.soft_rules.express_premium_total_over
    return RuleResult(rule="express_premium", kind="soft", passed=p <= limit, message=f"express premium {p:g}, limit {limit:g}")
