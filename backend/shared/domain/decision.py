"""The decision form the agent submits, and the reports produced when it is validated, executed and verified."""

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator

from shared.domain.planning import DemandAssumption, Option, PlanLine, TransferLine

DecisionType = Literal["accept", "modify", "reject", "investigate", "escalate"]


class DecisionReason(BaseModel):
    factor: str = Field(description="short name, e.g. open_po_ignored, budget, storage, shelf_life")
    finding: str = Field(description="what the evidence shows, with the numbers")
    evidence: list[str] = Field(default_factory=list, description="tool_call ids whose results support this")


class Decision(BaseModel):
    type: DecisionType
    node: str
    sku: str
    recommendation_id: Optional[str] = None
    lines: list[PlanLine] = Field(default_factory=list, description="purchase order lines to place")
    transfers: list[TransferLine] = Field(default_factory=list, description="stock to move from other dark stores")
    demand_assumption: Optional[DemandAssumption] = Field(
        default=None, description="only if you decided the forecast is wrong: the demand per day this plan is built on")
    option_id: Optional[str] = Field(default=None, description="id of the engine option this follows, if any")
    reasons: list[DecisionReason] = Field(min_length=1)
    risks: list[str] = Field(default_factory=list)
    confidence: Literal["low", "medium", "high"] = "medium"
    summary: str = Field(description="plain-language explanation for the buyer")
    questions_for_human: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _lines_match_type(self):
        if self.type == "modify" and not (self.lines or self.transfers):
            raise ValueError("a 'modify' decision needs at least one order line or transfer")
        if self.type in ("reject", "investigate", "escalate") and (self.lines or self.transfers):
            raise ValueError(f"a '{self.type}' decision must not contain order lines or transfers")
        return self

    @property
    def total_qty(self) -> int:
        return sum(line.qty for line in self.lines)


class RuleResult(BaseModel):
    rule: str
    kind: Literal["hard", "soft"]
    passed: bool
    message: str


class ValidationReport(BaseModel):
    passed: bool  # all hard rules pass
    requires_approval: bool  # any soft rule violated
    hard_failures: list[RuleResult]
    soft_violations: list[RuleResult]
    all_results: list[RuleResult]
    evaluation: Optional[Option] = None


class ExecutionLine(BaseModel):
    po_id: str
    supplier_id: str
    qty_requested: int
    qty_confirmed: int
    status: str  # confirmed | partially_confirmed | rejected | failed
    requested_delivery: str
    confirmed_delivery: Optional[str] = None
    unit_cost: float
    message: str = ""
    attempts: int = 1
    replayed: bool = False


class ExecutionResult(BaseModel):
    lines: list[ExecutionLine]

    @property
    def all_as_requested(self) -> bool:
        return all(ln.status == "confirmed" and ln.qty_confirmed == ln.qty_requested
                   and ln.confirmed_delivery == ln.requested_delivery for ln in self.lines)


class VerificationReport(BaseModel):
    status: Literal["OK", "DEGRADED_OK", "UNACCEPTABLE"]
    message: str
    differences: list[str]
    expected: dict
    actual: dict
    residual_need: float  # units still needed over the horizon after what was confirmed
