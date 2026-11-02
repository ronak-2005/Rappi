"""Planning queries (the agent's 'calculate' tools). Nothing here changes state."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlmodel import Session

from read_api.schemas.planning import PlanQuery
from read_api.server.deps import policy, session
from read_api.services import planning_service as p
from shared.config.policy import Policy

router = APIRouter(prefix="/nodes/{node}/skus/{sku}", tags=["planning"])


@router.get("/requirement")
def requirement(node: str, sku: str, recommendation_id: Optional[str] = None,
                s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_requirement(s, pol, node, sku, recommendation_id)


@router.get("/projection")
def projection(node: str, sku: str, recommendation_id: Optional[str] = None, days: Optional[int] = None,
               s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_projection(s, pol, node, sku, None, recommendation_id, days)


@router.post("/projection")
def projection_with_plan(node: str, sku: str, body: PlanQuery, days: Optional[int] = None,
                         s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_projection(s, pol, node, sku, body.plan, body.recommendation_id, days)


@router.get("/options")
def options(node: str, sku: str, recommendation_id: Optional[str] = None,
            s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_options(s, pol, node, sku, recommendation_id)


@router.post("/evaluate")
def evaluate(node: str, sku: str, body: PlanQuery, s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.evaluate(s, pol, node, sku, body.plan, body.recommendation_id)


@router.get("/data-quality")
def data_quality(node: str, sku: str, s: Session = Depends(session), pol: Policy = Depends(policy)):
    return p.get_data_quality(s, pol, node, sku)
