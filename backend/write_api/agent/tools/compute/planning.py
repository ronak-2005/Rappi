"""'Calculate' tools. The maths is done by the engine (via the Read API, or the local validator for
validate_plan). The model reads results; it never computes quantities itself."""

from typing import Optional

from pydantic import BaseModel, Field

from shared.db.session import read_write
from shared.domain.planning import DemandAssumption, PlanLine, TransferLine
from write_api.agent.tools.read.facts import NodeSku
from write_api.agent.tools.registry import Tool, ToolContext
from write_api.validation.validator import validate


class DemandArgs(BaseModel):
    demand_per_day: Optional[float] = Field(default=None, description="plan on this demand per day instead of the forecast (only if the evidence says the forecast is wrong)")
    demand_until_day: Optional[int] = Field(default=None, description="apply demand_per_day only for days < this offset (e.g. until a promotion ends)")

    def assumption(self) -> Optional[DemandAssumption]:
        return DemandAssumption(per_day=self.demand_per_day, until_day=self.demand_until_day) if self.demand_per_day else None


class PlanArgs(DemandArgs):
    lines: list[PlanLine] = Field(default_factory=list, description="purchase order lines; empty = buy nothing")
    transfers: list[TransferLine] = Field(default_factory=list, description="stock to move from other stores")


class ProjectionArgs(PlanArgs):
    days: Optional[int] = Field(default=None, description="days to show (default: the planning horizon)")


def _dq(a: DemandArgs) -> dict:
    return {"demand_per_day": a.demand_per_day, "demand_until_day": a.demand_until_day}


def _path(c: ToolContext) -> str:
    return f"/nodes/{c.node}/skus/{c.sku}"


def data_quality(_: NodeSku, c: ToolContext) -> dict:
    return c.read.get(f"{_path(c)}/data-quality")


def compute_requirement(a: DemandArgs, c: ToolContext) -> dict:
    r = c.read.get(f"{_path(c)}/requirement", recommendation_id=c.recommendation_id, **_dq(a))
    keep = ("demand_basis", "today", "arrival_day", "arrival_date", "review_period_days", "horizon_days", "demand_over_horizon",
            "safety_stock", "on_hand", "open_receipts_in_horizon", "open_receipts_after_horizon", "inventory_position",
            "net_requirement", "order_qty", "moq", "case_pack", "formula")
    return {k: r[k] for k in keep}


def project_inventory(a: ProjectionArgs, c: ToolContext) -> dict:
    d = a.assumption()
    body = {"plan": {"lines": [ln.model_dump() for ln in a.lines], "transfers": [t.model_dump() for t in a.transfers]},
            "recommendation_id": c.recommendation_id, "demand": d.model_dump() if d else None}
    p = c.read.post(f"{_path(c)}/projection", body, days=a.days)
    cols = ("date", "day", "available", "receipts", "demand", "sold", "lost", "expired", "close", "free_l",
            "over_capacity", "below_ss")
    return {"today": p["today"], "demand_basis": p["demand_basis"], "safety_stock": p["safety_stock"],
            "horizon_days": p["horizon_days"], "summary": p["summary"], "days": [{k: d[k] for k in cols} for d in p["days"]]}


def generate_options(a: DemandArgs, c: ToolContext) -> dict:
    o = c.read.get(f"{_path(c)}/options", recommendation_id=c.recommendation_id, **_dq(a))
    compact = []
    for x in o["options"]:
        compact.append({
            "option_id": x["id"], "kind": x["kind"], "label": x["label"], "lines": x["plan"]["lines"],
            "transfers": x["plan"]["transfers"], "total_qty": x["total_qty"], "transfer_qty": x["transfer_qty"], "purchase_cost": x["purchase_cost"], "express_premium": x["express_premium"],
            "decision_cost": x["decision_cost"], "lost_units": x["lost_units"], "expired_units": x["expired_units"],
            "waste_pct": x["waste_pct"], "min_stock": x["min_close"], "end_stock": x["end_close"],
            "hard_rules_ok": x["hard_ok"], "failed_hard_checks": [k for k, v in x["checks"].items() if not v],
            "soft_issues_needing_approval": x["soft_issues"], "notes": x["notes"],
        })
    return {"today": o["today"], "demand_basis": o["demand_basis"], "ranking": o["ranking"], "options": compact}


def analyze_demand(_: NodeSku, c: ToolContext) -> dict:
    return c.read.get(f"{_path(c)}/demand-signal")


def validate_plan(a: PlanArgs, c: ToolContext) -> dict:
    """Dry run of the real rulebook. Nothing is written."""
    with read_write(c.db_file) as s:
        r = validate(s, c.policy, c.node, c.sku, a.lines, c.recommendation_id, a.transfers, a.assumption())
    return {"passes_hard_rules": r.passed, "needs_human_approval": r.requires_approval,
            "hard_failures": [x.model_dump() for x in r.hard_failures],
            "soft_violations": [x.model_dump() for x in r.soft_violations]}


TOOLS = [
    Tool("check_data_quality", "compute", "Sanity checks on the data (phantom stock, stale count, censored demand, forecast vs sales). Run before trusting the numbers.", NodeSku, data_quality),
    Tool("analyze_demand", "compute", "Recent sales vs the forecast: averages, elevated days, promotions covering them, stockout days, a classification (sustained_increase / promotion / one_off_spike / ...) and a suggested demand assumption.", NodeSku, analyze_demand),
    Tool("compute_requirement", "compute", "The real net requirement with every term (horizon, demand, safety stock, on hand, open POs in time) and the order qty rounded to MOQ/case pack. Optionally on a demand assumption.", DemandArgs, compute_requirement),
    Tool("project_inventory", "compute", "Day-by-day stock projection if we do nothing (no lines) or if we execute the given lines: stock, lost sales, expiry, storage overflow, safety-stock breaches.", ProjectionArgs, project_inventory),
    Tool("generate_options", "compute", "Candidate plans computed by the engine (standard, express, bridge, two drops, within budget, waste-free, transfer from another store, do nothing, as recommended) with costs and rule checks, best first. Optionally on a demand assumption.", DemandArgs, generate_options),
    Tool("validate_plan", "compute", "Dry-run the rulebook on a plan before submitting it: hard failures block it, soft violations need human approval.", PlanArgs, validate_plan),
]
