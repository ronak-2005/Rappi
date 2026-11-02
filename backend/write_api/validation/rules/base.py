"""What every rule receives and returns. A rule is a function RuleInput → RuleResult."""

from dataclasses import dataclass, field
from typing import Callable

from shared.config.policy import Policy
from shared.domain.decision import RuleResult
from shared.domain.planning import Option, PlanLine
from shared.engine.options import OptionContext


@dataclass
class RuleInput:
    evaluation: Option  # engine evaluation of the plan (projection, costs, per-check flags)
    ctx: OptionContext
    lines: list[PlanLine]
    policy: Policy
    duplicate_po_ids: list[str] = field(default_factory=list)


Rule = Callable[[RuleInput], RuleResult]
