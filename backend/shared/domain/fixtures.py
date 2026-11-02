"""Fixture file format: a scenario 'world', its trigger, supplier behaviour and the expected outcome.

Fixtures are YAML files in backend/fixtures/. Relative day offsets ("arrives_in_days: 2") are
converted to real dates from the fixture's `today` when loaded. The same files drive the UI demo,
the integration tests and the evals.
"""

from datetime import date
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator


def _exactly_one_series(spec, what: str):
    """A series is given either as a constant per day or as an explicit daily list, never both or neither."""
    if (spec.units_per_day is None) == (spec.daily is None):
        raise ValueError(f"{what} needs exactly one of units_per_day or daily")
    return spec


class NodeSpec(BaseModel):
    id: str
    name: str
    city: str = ""
    transfer_lead_days: int = 1
    transfer_cost_per_unit: float = 0.05


class ZoneSpec(BaseModel):
    node: str
    zone: Literal["ambient", "chilled", "frozen"]
    capacity_l: float
    other_skus_used_l: float = 0  # constant litres used by other SKUs every day


class SkuSpec(BaseModel):
    id: str
    name: str
    category: str
    zone: Literal["ambient", "chilled", "frozen"]
    unit_volume_l: float = 1.0
    shelf_life_days: int = 365
    criticality: Literal["high", "medium", "low"] = "medium"
    unit_margin: float = 0.0
    review_period_days: int = 7


class InventorySpec(BaseModel):
    node: str
    sku: str
    on_hand: int
    last_counted_days_ago: int = 0
    remaining_shelf_life_days: int | None = None


class ForecastSpec(BaseModel):
    node: str
    sku: str
    sigma: float
    units_per_day: float | None = None
    daily: list[float] | None = None  # day 0 (today) onwards
    days: int = 30

    @model_validator(mode="after")
    def _one_of(self):
        return _exactly_one_series(self, "forecast")


class SalesSpec(BaseModel):
    node: str
    sku: str
    units_per_day: int | None = None
    daily: list[int] | None = None  # oldest → yesterday
    days: int = 14
    stocked_out_days_ago: list[int] = Field(default_factory=list)  # 1 = yesterday

    @model_validator(mode="after")
    def _one_of(self):
        return _exactly_one_series(self, "sales_history")


class SupplierSpec(BaseModel):
    id: str
    name: str
    active: bool = True
    delivery_weekdays: list[int] = Field(default_factory=lambda: list(range(7)))  # 0 = Monday
    cutoff_hour: int = 14
    fill_rate: float = 1.0
    on_time_rate: float = 1.0
    lead_time_sigma_days: float = 0.0
    orders_observed: int = 20


class TermSpec(BaseModel):
    supplier: str
    sku: str
    unit_cost: float
    moq: int = 1
    case_pack: int = 1
    lead_time_days: int
    express_lead_days: int | None = None
    express_premium_per_unit: float = 0.0
    max_qty: int = 1_000_000
    remaining_shelf_life_days: int | None = None


class OpenPOSpec(BaseModel):
    id: str
    node: str
    sku: str
    supplier: str
    qty: int
    unit_cost: float
    arrives_in_days: int
    ordered_days_ago: int = 1
    status: Literal["sent", "confirmed", "partially_confirmed"] = "confirmed"
    qty_confirmed: int | None = None
    mode: Literal["standard", "express"] = "standard"
    remaining_shelf_life_days: int | None = None


class BudgetSpec(BaseModel):
    node: str
    category: str
    total: float
    committed: float = 0
    period_days: int = 30


class PromotionSpec(BaseModel):
    node: str
    sku: str
    starts_in_days: int  # negative = already running
    ends_in_days: int
    uplift_pct: float
    description: str = ""


class WorldSpec(BaseModel):
    nodes: list[NodeSpec]
    storage_zones: list[ZoneSpec]
    skus: list[SkuSpec]
    inventory: list[InventorySpec]
    forecasts: list[ForecastSpec]
    sales_history: list[SalesSpec] = Field(default_factory=list)
    suppliers: list[SupplierSpec]
    supplier_terms: list[TermSpec]
    open_pos: list[OpenPOSpec] = Field(default_factory=list)
    budgets: list[BudgetSpec] = Field(default_factory=list)
    promotions: list[PromotionSpec] = Field(default_factory=list)


class RecommendationSpec(BaseModel):
    id: str
    node: str
    sku: str
    qty: int
    supplier: str | None = None  # supplier the recommending system assumed
    source: str = "replenishment_engine"


class SupplierEventSpec(BaseModel):
    id: str
    po_id: str
    confirmed_qty: int
    message: str
    unavailable_days: int = 14  # the supplier can't supply more of this SKU for this long


class DemandAlertSpec(BaseModel):
    id: str
    node: str
    sku: str
    message: str


class TriggerSpec(BaseModel):
    type: Literal["recommendation", "supplier_event", "demand_alert"]
    recommendation: RecommendationSpec | None = None
    supplier_event: SupplierEventSpec | None = None
    demand_alert: DemandAlertSpec | None = None

    @property
    def ref(self) -> str:
        return (self.recommendation or self.supplier_event or self.demand_alert).id


class BehaviourSpec(BaseModel):
    """How the mock supplier answers new purchase orders."""

    mode: Literal["confirm", "partial", "reject", "delay", "timeout_once", "price_change"] = "confirm"
    ratio: float = 1.0  # partial: share of qty confirmed
    delay_days: int = 0
    new_unit_cost: float | None = None
    apply_to: Literal["first", "all"] = "all"  # 'first' = only the first PO to this supplier behaves this way


class ExpectedSpec(BaseModel):
    """Hand-computed ground truth used by graders. See `notes` for the arithmetic."""

    decision: list[Literal["accept", "modify", "reject", "investigate", "escalate"]]
    qty_range: tuple[int, int] | None = None  # total PURCHASED qty across all order lines
    lines: int | None = None
    transfers: int | None = None  # number of transfer lines in the decision
    transfer_qty_range: tuple[int, int] | None = None
    demand_per_day_range: tuple[float, float] | None = None  # the demand assumption the decision should use
    supplier: str | None = None  # expected supplier when it matters (single-line decisions)
    replan_qty_range: tuple[int, int] | None = None  # extra qty ordered after a failed verification
    required_tools: list[str] = Field(default_factory=list)
    approval_required: bool | None = None
    approval_response: Literal["approve", "reject"] = "approve"
    pos_created: int | None = None
    supplier_orders: int | None = None
    final_verification: list[str] = Field(default_factory=list)
    recovery: Literal["replan", "escalate"] | None = None
    key_factors: list[str] = Field(default_factory=list)
    notes: str = ""


class FixtureSpec(BaseModel):
    id: str
    scenario: Literal["S1", "S2", "S3", "S4"]
    title: str
    description: str
    today: date
    now_hour: int = 10
    world: WorldSpec
    trigger: TriggerSpec
    supplier_behaviour: dict[str, BehaviourSpec] = Field(default_factory=dict)
    expected: ExpectedSpec


def parse_fixture(text: str) -> FixtureSpec:
    return FixtureSpec.model_validate(yaml.safe_load(text))


def fixtures_dir():
    from shared.config.settings import get_settings

    settings = get_settings()
    return settings.resolve(settings.fixtures_dir)


def load_fixture_file(fixture_id: str) -> FixtureSpec:
    path = fixtures_dir() / f"{fixture_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"fixture '{fixture_id}' not found in {fixtures_dir()}")
    return parse_fixture(path.read_text())


def list_fixture_files() -> list[FixtureSpec]:
    return [parse_fixture(p.read_text()) for p in sorted(fixtures_dir().glob("*.yaml"))]
