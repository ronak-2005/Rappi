"""GET: facts about the world (what the agent's 'look up' tools call)."""

from fastapi import APIRouter, Depends
from sqlmodel import Session

from read_api.repositories import catalog_repository
from read_api.server.deps import session
from read_api.services import facts_service as f

router = APIRouter(tags=["facts"])


@router.get("/situation/recommendations/{rec_id}")
def situation(rec_id: str, s: Session = Depends(session)):
    return f.situation(s, rec_id)


@router.get("/situation/supplier-events/{event_id}")
def supplier_event(event_id: str, s: Session = Depends(session)):
    return f.supplier_event_situation(s, event_id)


@router.get("/situation/demand-alerts/{alert_id}")
def demand_alert(alert_id: str, s: Session = Depends(session)):
    return f.demand_alert_situation(s, alert_id)


@router.get("/recommendations")
def recommendations(s: Session = Depends(session)):
    return [r.model_dump() for r in catalog_repository.recommendations(s)]


@router.get("/skus/{sku}")
def sku_profile(sku: str, s: Session = Depends(session)):
    return f.sku_profile(s, sku)


@router.get("/skus/{sku}/suppliers")
def supplier_terms(sku: str, s: Session = Depends(session)):
    return f.supplier_terms(s, sku)


@router.get("/skus/{sku}/stock-by-node")
def stock_by_node(sku: str, exclude_node: str = "", s: Session = Depends(session)):
    return f.other_nodes_stock(s, sku, exclude_node)


@router.get("/suppliers/{supplier_id}/performance")
def supplier_performance(supplier_id: str, s: Session = Depends(session)):
    return f.supplier_performance(s, supplier_id)


@router.get("/nodes/{node}/skus/{sku}/inventory")
def inventory(node: str, sku: str, s: Session = Depends(session)):
    return f.inventory(s, node, sku)


@router.get("/nodes/{node}/skus/{sku}/purchase-orders/open")
def open_pos(node: str, sku: str, s: Session = Depends(session)):
    return f.open_purchase_orders(s, node, sku)


@router.get("/nodes/{node}/skus/{sku}/sales")
def sales(node: str, sku: str, days: int = 14, s: Session = Depends(session)):
    return f.sales_history(s, node, sku, days)


@router.get("/nodes/{node}/skus/{sku}/forecast")
def forecast(node: str, sku: str, days: int = 14, s: Session = Depends(session)):
    return f.forecast(s, node, sku, days)


@router.get("/nodes/{node}/skus/{sku}/promotions")
def promotions(node: str, sku: str, s: Session = Depends(session)):
    return f.promotions(s, node, sku)


@router.get("/nodes/{node}/budget")
def budget(node: str, category: str, s: Session = Depends(session)):
    return f.budget(s, node, category)


@router.get("/nodes/{node}/storage/{zone}")
def storage(node: str, zone: str, days: int = 10, s: Session = Depends(session)):
    return f.storage_status(s, node, zone, days)
