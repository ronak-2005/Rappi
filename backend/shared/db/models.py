"""Database tables. Shared schema; read_api only SELECTs, write_api INSERTs/UPDATEs.

Units: stock in units; storage in litres (unit_volume_l × units), so zones are shared across SKUs.
Dates are simulated: the `world` row holds the fixture's "today".
"""

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column, UniqueConstraint
from sqlmodel import Field, SQLModel


class World(SQLModel, table=True):
    """Single row: which scenario is loaded and what 'today' is."""
    id: int = Field(default=1, primary_key=True)
    fixture_id: str
    today: date
    now_hour: int = 10


# ---------- master data ----------
class Node(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    city: str = ""


class StorageZone(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str = Field(index=True)
    zone: str  # ambient | chilled | frozen
    capacity_l: float


class ZoneOccupancy(SQLModel, table=True):
    """Litres used by OTHER SKUs per day (simplification of a full multi-SKU simulation)."""
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str = Field(index=True)
    zone: str
    day: date
    used_l: float


class Sku(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    category: str
    zone: str
    unit_volume_l: float = 1.0
    shelf_life_days: int = 365
    criticality: str = "medium"  # high | medium | low
    unit_margin: float = 0.0
    review_period_days: int = 7


class Supplier(SQLModel, table=True):
    id: str = Field(primary_key=True)
    name: str
    active: bool = True
    delivery_weekdays: list[int] = Field(default_factory=lambda: list(range(7)), sa_column=Column(JSON))
    cutoff_hour: int = 14
    fill_rate: float = 1.0
    on_time_rate: float = 1.0
    lead_time_sigma_days: float = 0.0
    orders_observed: int = 20


class SupplierTerm(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    supplier_id: str = Field(index=True)
    sku_id: str = Field(index=True)
    unit_cost: float
    moq: int = 1
    case_pack: int = 1
    lead_time_days: int
    express_available: bool = False
    express_lead_days: Optional[int] = None
    express_premium_per_unit: float = 0.0
    max_qty: int = 1_000_000
    remaining_shelf_life_days: Optional[int] = None  # shelf life left when goods arrive


# ---------- operational data ----------
class Inventory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str = Field(index=True)
    sku_id: str = Field(index=True)
    on_hand: int
    last_counted_at: date
    remaining_shelf_life_days: Optional[int] = None  # of the stock currently on hand


class SalesHistory(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str = Field(index=True)
    sku_id: str = Field(index=True)
    day: date
    units: int
    stocked_out: bool = False


class Forecast(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str = Field(index=True)
    sku_id: str = Field(index=True)
    day: date
    units: float
    sigma: float


class Promotion(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str
    sku_id: str
    start: date
    end: date
    uplift_pct: float
    description: str = ""


class Budget(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    node_id: str
    category: str
    period_start: date
    period_end: date
    total: float
    committed: float


class Recommendation(SQLModel, table=True):
    id: str = Field(primary_key=True)
    node_id: str
    sku_id: str
    qty: int
    supplier_id: Optional[str] = None
    source: str = "replenishment_engine"
    created_at: date
    status: str = "open"  # open | accepted | modified | rejected | investigating | escalated


class PurchaseOrder(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    id: str = Field(primary_key=True)
    node_id: str = Field(index=True)
    sku_id: str = Field(index=True)
    supplier_id: str
    qty_ordered: int
    qty_confirmed: Optional[int] = None
    unit_cost: float
    mode: str = "standard"  # standard | express
    # draft | pending_approval | sent | confirmed | partially_confirmed | rejected | received | cancelled
    status: str
    order_date: date
    expected_delivery: date
    remaining_shelf_life_days: Optional[int] = None
    idempotency_key: Optional[str] = None
    run_id: Optional[str] = Field(default=None, index=True)
    created_by: str = "system"  # system | agent | human
    notes: str = ""


class POEvent(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    po_id: str = Field(index=True)
    at: datetime
    type: str  # sent | confirmed | partially_confirmed | rejected | delayed | timeout | retried | cancelled
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Transfer(SQLModel, table=True):
    id: str = Field(primary_key=True)
    from_node: str
    to_node: str
    sku_id: str
    qty: int
    eta: date
    status: str = "planned"
    run_id: Optional[str] = None


# ---------- agent bookkeeping ----------
class AgentRun(SQLModel, table=True):
    id: str = Field(primary_key=True)
    fixture_id: str
    trigger_type: str  # recommendation | supplier_event | demand_alert
    trigger_ref: str
    status: str  # running | awaiting_approval | completed | escalated | failed | cancelled
    state: str  # current state-machine state
    llm_mode: str
    llm_model: str = ""
    decision: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    outcome: Optional[dict[str, Any]] = Field(default=None, sa_column=Column(JSON))
    tool_calls: int = 0
    revisions: int = 0
    replans: int = 0
    started_at: datetime
    finished_at: Optional[datetime] = None
    error: Optional[str] = None


class TraceStep(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    run_id: str = Field(index=True)
    seq: int
    at: datetime
    state: str
    kind: str  # llm_message | tool_call | tool_result | gate | validation | approval | action | verification | info | error
    name: str = ""
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))


class Approval(SQLModel, table=True):
    id: str = Field(primary_key=True)
    run_id: str = Field(index=True)
    reasons: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    plan: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = "pending"  # pending | approved | rejected | edited
    resolved_by: Optional[str] = None
    comment: str = ""
    created_at: datetime
    resolved_at: Optional[datetime] = None
