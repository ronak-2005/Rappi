"""'Look up' tools: each is one GET on the Read API. node/sku default to the run's situation."""

from typing import Optional

from pydantic import BaseModel, Field

from write_api.agent.tools.registry import Tool, ToolContext


class NodeSku(BaseModel):
    node: Optional[str] = Field(default=None, description="dark store id; defaults to the situation's node")
    sku: Optional[str] = Field(default=None, description="product id; defaults to the situation's SKU")


class NoArgs(BaseModel):
    pass


class SkuOnly(BaseModel):
    sku: Optional[str] = None


class Days(NodeSku):
    days: int = Field(default=14, ge=1, le=60)


class SupplierArg(BaseModel):
    supplier_id: str


class StorageArgs(BaseModel):
    node: Optional[str] = None
    zone: Optional[str] = Field(default=None, description="ambient | chilled | frozen; defaults to the SKU's zone")
    days: int = Field(default=10, ge=1, le=30)


def _ns(a, c: ToolContext):
    return a.node or c.node, a.sku or c.sku


def situation(_: NoArgs, c: ToolContext) -> dict:
    path = {"recommendation": "recommendations", "supplier_event": "supplier-events",
            "demand_alert": "demand-alerts"}[c.trigger_type]
    return c.read.get(f"/situation/{path}/{c.trigger_ref}")


def sku_profile(a: SkuOnly, c: ToolContext) -> dict:
    return c.read.get(f"/skus/{a.sku or c.sku}")


def inventory(a: NodeSku, c: ToolContext) -> dict:
    n, s = _ns(a, c)
    return c.read.get(f"/nodes/{n}/skus/{s}/inventory")


def open_pos(a: NodeSku, c: ToolContext) -> dict:
    n, s = _ns(a, c)
    return c.read.get(f"/nodes/{n}/skus/{s}/purchase-orders/open")


def sales(a: Days, c: ToolContext) -> dict:
    n, s = _ns(a, c)
    return c.read.get(f"/nodes/{n}/skus/{s}/sales", days=a.days)


def forecast(a: Days, c: ToolContext) -> dict:
    n, s = _ns(a, c)
    return c.read.get(f"/nodes/{n}/skus/{s}/forecast", days=a.days)


def promotions(a: NodeSku, c: ToolContext) -> dict:
    n, s = _ns(a, c)
    return c.read.get(f"/nodes/{n}/skus/{s}/promotions")


def supplier_terms(a: SkuOnly, c: ToolContext) -> dict:
    return c.read.get(f"/skus/{a.sku or c.sku}/suppliers")


def supplier_performance(a: SupplierArg, c: ToolContext) -> dict:
    return c.read.get(f"/suppliers/{a.supplier_id}/performance")


def budget(a: NodeSku, c: ToolContext) -> dict:
    n, s = _ns(a, c)
    category = c.read.get(f"/skus/{s}")["category"]
    return c.read.get(f"/nodes/{n}/budget", category=category)


def storage(a: StorageArgs, c: ToolContext) -> dict:
    zone = a.zone or c.read.get(f"/skus/{c.sku}")["zone"]
    return c.read.get(f"/nodes/{a.node or c.node}/storage/{zone}", days=a.days)


def other_nodes(a: SkuOnly, c: ToolContext) -> dict:
    return c.read.get(f"/skus/{a.sku or c.sku}/stock-by-node", exclude_node=c.node)


TOOLS = [
    Tool("get_situation", "read", "What triggered this run: a recommendation to review, a supplier's shortfall message on a PO, or a demand alert.", NoArgs, situation),
    Tool("get_sku_profile", "read", "Product facts: storage zone, unit volume, shelf life, criticality, unit margin, review period.", SkuOnly, sku_profile),
    Tool("get_inventory", "read", "Stock on hand now, when it was last physically counted, and remaining shelf life.", NodeSku, inventory),
    Tool("get_open_pos", "read", "Purchase orders already placed and not yet received: qty, status, expected delivery date.", NodeSku, open_pos),
    Tool("get_sales_history", "read", "Daily units sold for the last N days, with stockout days flagged (sales on stockout days understate demand).", Days, sales),
    Tool("get_forecast", "read", "Forecast units per day (and uncertainty sigma) for the next N days.", Days, forecast),
    Tool("get_promotions", "read", "Promotions running now, recently, or planned for this product at this store.", NodeSku, promotions),
    Tool("get_supplier_terms", "read", "Every supplier for this SKU: unit cost, MOQ, case pack, lead time, express option, delivery weekdays, cut-off hour, earliest arrival, fill rate.", SkuOnly, supplier_terms),
    Tool("get_supplier_performance", "read", "A supplier's observed fill rate and on-time rate.", SupplierArg, supplier_performance),
    Tool("get_budget", "read", "Budget for the SKU's category at this store: total, committed, remaining.", NodeSku, budget),
    Tool("get_storage_status", "read", "Free storage (litres) per day in the SKU's temperature zone, after other products' use.", StorageArgs, storage),
    Tool("get_other_nodes_stock", "read", "Other dark stores' stock of this SKU and how much each can SPARE after covering its own need (transfers arrive in 1 day).", SkuOnly, other_nodes),
]
