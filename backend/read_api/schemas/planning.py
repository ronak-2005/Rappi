"""Request bodies for read-side queries that need a structured input (a plan to evaluate).
POST is used only because a plan doesn't fit in a URL; these endpoints change nothing."""

from pydantic import BaseModel

from shared.domain.planning import DemandAssumption, Plan


class PlanQuery(BaseModel):
    plan: Plan
    recommendation_id: str | None = None
    demand: DemandAssumption | None = None  # use this demand instead of the forecast
