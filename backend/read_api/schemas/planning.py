"""Request bodies for read-side queries that need a structured input (a plan to evaluate).
POST is used only because a plan doesn't fit in a URL; these endpoints change nothing."""

from typing import Optional

from pydantic import BaseModel

from shared.domain.planning import Plan


class PlanQuery(BaseModel):
    plan: Plan
    recommendation_id: Optional[str] = None
