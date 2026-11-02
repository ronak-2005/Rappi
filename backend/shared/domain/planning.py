"""Planning types used by the engine, the read_api (to show them) and the write_api (to validate them).

Days are integer offsets from the simulated 'today' (0 = today). Services convert them to dates.
"""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class Receipt(BaseModel):
    """Stock arriving on a given day (an open PO, a planned order line, or a transfer)."""
    day: int
    qty: float
    remaining_shelf_life_days: Optional[int] = None  # shelf life left on arrival; None = non-perishable
    source: str  # e.g. "PO-1001" or "plan:line1"
    is_new: bool = False  # True = part of the plan being evaluated (waste is attributed to it)


class SupplierOffer(BaseModel):
    """Everything about buying one SKU from one supplier."""
    supplier_id: str
    supplier_name: str = ""
    active: bool = True
    unit_cost: float
    moq: int = 1
    case_pack: int = 1
    lead_time_days: int
    express_lead_days: Optional[int] = None
    express_premium_per_unit: float = 0.0
    max_qty: int = 1_000_000
    remaining_shelf_life_days: Optional[int] = None
    delivery_weekdays: list[int] = Field(default_factory=lambda: list(range(7)))
    cutoff_hour: int = 14
    fill_rate: float = 1.0
    on_time_rate: float = 1.0
    lead_time_sigma_days: float = 0.0


class PlanLine(BaseModel):
    supplier_id: str
    qty: int
    mode: Literal["standard", "express"] = "standard"
    delivery_day: Optional[int] = None  # None = earliest possible for the mode


class Plan(BaseModel):
    lines: list[PlanLine] = Field(default_factory=list)

    @property
    def total_qty(self) -> int:
        return sum(line.qty for line in self.lines)


class ProjectionDay(BaseModel):
    day: int
    open: float
    receipts: float
    expired: float
    available: float  # stock on the shelf after receipts and write-offs, before sales (peak of the day)
    demand: float
    sold: float
    lost: float
    close: float
    volume_l: float
    free_l: float
    over_capacity: bool
    below_ss: bool


class Projection(BaseModel):
    horizon_days: int
    safety_stock: float
    days: list[ProjectionDay]
    lost_units: float  # within the horizon
    first_stockout_day: Optional[int]
    expired_units_new: float  # expired units that came from the plan being evaluated (whole simulation)
    expired_units_total: float
    over_capacity_days: list[int]
    below_ss_days: list[int]  # within [check_from_day, horizon)
    min_close: float
    end_close: float  # close on the last horizon day


class Requirement(BaseModel):
    """How much we really need, with every term shown so it can be explained."""
    arrival_day: int
    review_period_days: int
    horizon_days: int
    demand_over_horizon: float
    safety_stock: float
    on_hand: float
    open_receipts_in_horizon: float
    open_receipts_after_horizon: float
    inventory_position: float
    net_requirement: float  # can be negative = no need
    order_qty: int  # rounded up to case pack and MOQ (0 if no need)
    moq: int
    case_pack: int
    rounded_for_supplier: str = ""  # whose MOQ / case pack `order_qty` uses


class Option(BaseModel):
    """A candidate plan with its consequences and feasibility, produced by the engine."""
    id: str
    kind: str  # do_nothing | as_recommended | standard | express | bridge | two_drops | within_budget | waste_free
    label: str
    plan: Plan
    total_qty: int
    purchase_cost: float
    express_premium: float
    decision_cost: float  # cost that differs between options (see engine/cost.py)
    cost_breakdown: dict[str, float]
    lost_units: float
    expired_units: float
    waste_pct: float
    min_close: float
    end_close: float
    over_capacity_days: list[int]
    below_ss_days: list[int]
    checks: dict[str, bool]  # per-rule pass/fail, e.g. {"capacity": True, "moq": True, ...}
    hard_ok: bool
    soft_issues: list[str]
    notes: list[str] = Field(default_factory=list)


class Anomaly(BaseModel):
    code: str
    severity: Literal["high", "medium", "low"]
    message: str
    evidence: dict = Field(default_factory=dict)
