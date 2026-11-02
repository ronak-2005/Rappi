"""'Calculate' tools. The maths is done by the engine (via the Read API, or the local validator for
validate_plan). The model reads results; it never computes quantities itself."""

from typing import Optional

from pydantic import BaseModel, Field

from shared.db.session import read_write
from shared.domain.planning import PlanLine
from write_api.agent.tools.read.facts import NodeSku
from write_api.agent.tools.registry import Tool, ToolContext
from write_api.validation.validator import validate


class PlanArgs(BaseModel):
    lines: list[PlanLine] = Field(default_factory=list, description="order lines; empty = do nothing")


class ProjectionArgs(PlanArgs):
    days: Optional[int] = Field(default=None, description="days to show (default: the planning horizon)")


def _path(c: ToolContext) -> str:
    return f"/nodes/{c.node}/skus/{c.sku}"


def data_quality(_: NodeSku, c: ToolContext) -> dict:
    return c.read.get(f"{_path(c)}/data-quality")


def compute_requirement(_: NodeSku, c: ToolContext) -> dict:
    r = c.read.get(f"{_path(c)}/requirement", recommendation_id=c.recommendation_id)
    keep = ("today", "arrival_day", "arrival_date", "review_period_days", "horizon_days", "demand_over_horizon",
            "safety_stock", "on_hand", "open_receipts_in_horizon", "open_receipts_after_horizon", "inventory_position",
            "net_requirement", "order_qty", "moq", "case_pack", "formula")
    return {k: r[k] for k in keep}


def project_inventory(a: ProjectionArgs, c: ToolContext) -> dict:
    body = {"plan": {"lines": [ln.model_dump() for ln in a.lines]}, "recommendation_id": c.recommendation_id}
    p = c.read.post(f"{_path(c)}/projection", body, days=a.days)
    cols = ("date", "day", "available", "receipts", "demand", "sold", "lost", "expired", "close", "free_l",
            "over_capacity", "below_ss")
    return {"today": p["today"], "safety_stock": p["safety_stock"], "horizon_days": p["horizon_days"],
            "summary": p["summary"], "days": [{k: d[k] for k in cols} for d in p["days"]]}


def generate_options(_: NodeSku, c: ToolContext) -> dict:
    o = c.read.get(f"{_path(c)}/options", recommendation_id=c.recommendation_id)
    compact = []
    for x in o["options"]:
        compact.append({
            "option_id": x["id"], "kind": x["kind"], "label": x["label"], "lines": x["plan"]["lines"],
            "total_qty": x["total_qty"], "purchase_cost": x["purchase_cost"], "express_premium": x["express_premium"],
            "decision_cost": x["decision_cost"], "lost_units": x["lost_units"], "expired_units": x["expired_units"],
            "waste_pct": x["waste_pct"], "min_stock": x["min_close"], "end_stock": x["end_close"],
            "hard_rules_ok": x["hard_ok"], "failed_hard_checks": [k for k, v in x["checks"].items() if not v],
            "soft_issues_needing_approval": x["soft_issues"], "notes": x["notes"],
        })
    return {"today": o["today"], "ranking": o["ranking"], "options": compact}


def validate_plan(a: PlanArgs, c: ToolContext) -> dict:
    """Dry run of the real rulebook. Nothing is written."""
    with read_write(c.db_file) as s:
        r = validate(s, c.policy, c.node, c.sku, a.lines, c.recommendation_id)
    return {"passes_hard_rules": r.passed, "needs_human_approval": r.requires_approval,
            "hard_failures": [x.model_dump() for x in r.hard_failures],
            "soft_violations": [x.model_dump() for x in r.soft_violations]}


TOOLS = [
    Tool("check_data_quality", "compute", "Sanity checks on the data (phantom stock, stale count, censored demand, forecast vs sales). Run before trusting the numbers.", NodeSku, data_quality),
    Tool("compute_requirement", "compute", "The real net requirement with every term (horizon, demand, safety stock, on hand, open POs in time) and the order qty rounded to MOQ/case pack.", NodeSku, compute_requirement),
    Tool("project_inventory", "compute", "Day-by-day stock projection if we do nothing (no lines) or if we execute the given lines: stock, lost sales, expiry, storage overflow, safety-stock breaches.", ProjectionArgs, project_inventory),
    Tool("generate_options", "compute", "Candidate plans computed by the engine (standard, express, bridge, two drops, within budget, waste-free, do nothing, as recommended) with costs and rule checks, best first.", NodeSku, generate_options),
    Tool("validate_plan", "compute", "Dry-run the rulebook on a plan before submitting it: hard failures block it, soft violations need human approval.", PlanArgs, validate_plan),
]
