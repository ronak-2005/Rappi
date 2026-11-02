"""Write API request bodies."""

from typing import Literal, Optional

from pydantic import BaseModel, Field


class StartRun(BaseModel):
    recommendation_id: Optional[str] = Field(default=None, description="defaults to the loaded fixture's recommendation")
    fixture_id: Optional[str] = Field(default=None, description="if set, (re)load this scenario world first")
    llm_env: Optional[str] = Field(default=None, description="alternative env file (relative to backend/), e.g. evals/llm/x.env")
    llm_mode: Optional[Literal["live", "baseline", "scripted"]] = Field(default=None, description="override LLM_MODE")


class ResolveApproval(BaseModel):
    decision: Literal["approve", "reject", "edit"]
    comment: str = ""
    by: str = "buyer"
    lines: Optional[list[dict]] = None  # for 'edit'
