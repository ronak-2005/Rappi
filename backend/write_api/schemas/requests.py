"""Write API request bodies."""

from typing import Literal

from pydantic import BaseModel, Field

LLMMode = Literal["live", "baseline", "scripted"]


class StartRun(BaseModel):
    recommendation_id: str | None = Field(default=None, description="defaults to the loaded fixture's recommendation")
    fixture_id: str | None = Field(default=None, description="if set, (re)load this scenario world first")
    llm_env: str | None = Field(
        default=None, description="alternative env file (relative to backend/), e.g. evals/llm/x.env"
    )
    llm_mode: LLMMode | None = Field(default=None, description="override LLM_MODE")


class ResolveApproval(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    comment: str = ""
    by: str = "buyer"
    lines: list[dict] | None = None  # for 'edit'


class SupplierEventIn(BaseModel):
    po_id: str
    confirmed_qty: int
    message: str
    unavailable_days: int = 14
    run_agent: bool = True
    llm_mode: LLMMode | None = None


class DemandAlertIn(BaseModel):
    node: str
    sku: str
    message: str
    run_agent: bool = True
    llm_mode: LLMMode | None = None
