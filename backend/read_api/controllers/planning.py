"""Planning queries (the agent's 'calculate' tools). Nothing here changes state."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from read_api.schemas.planning import PlanQuery
from read_api.server.deps import policy, session
from read_api.services import planning_service as p
from shared.config.policy import Policy
from shared.domain.planning import DemandAssumption

router = APIRouter(prefix="/nodes/{node}/skus/{sku}", tags=["planning"])


def _demand(per_day: Optional[float], until_day: Optional[int]) -> Optional[DemandAssumption]:
    return DemandAssumption(per_day=per_day, until_day=until_day) if per_day is not None else None


@router.get("/requirement")
def requirement(node: str, sku: str, recommendation_id: Optional[str] = None, demand_per_day: Optional[float] = None,
                demand_until_day: Optional[int] = None, s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_requirement(s, pol, node, sku, recommendation_id, _demand(demand_per_day, demand_until_day))


@router.get("/projection")
def projection(node: str, sku: str, recommendation_id: Optional[str] = None, days: Optional[int] = None,
               demand_per_day: Optional[float] = None, demand_until_day: Optional[int] = None,
               s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_projection(s, pol, node, sku, None, recommendation_id, days, _demand(demand_per_day, demand_until_day))


@router.post("/projection")
def projection_with_plan(node: str, sku: str, body: PlanQuery, days: Optional[int] = None,
                         s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_projection(s, pol, node, sku, body.plan, body.recommendation_id, days, body.demand)


@router.get("/options")
def options(node: str, sku: str, recommendation_id: Optional[str] = None, demand_per_day: Optional[float] = None,
            demand_until_day: Optional[int] = None, s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_options(s, pol, node, sku, recommendation_id, _demand(demand_per_day, demand_until_day))


@router.post("/evaluate")
def evaluate(node: str, sku: str, body: PlanQuery, s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.evaluate(s, pol, node, sku, body.plan, body.recommendation_id, body.demand)


@router.get("/data-quality")
def data_quality(node: str, sku: str, s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_data_quality(s, pol, node, sku)


@router.get("/demand-signal")
def demand_signal(node: str, sku: str, s: Session = Depends(session)):
    return p.get_demand_signal(s, node, sku)
