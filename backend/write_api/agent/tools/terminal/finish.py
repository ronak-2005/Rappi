"""'Finish' tools. The orchestrator intercepts these: the model hands over a decision (or an
escalation) and code takes it from there. There is deliberately no tool that places an order."""

from typing import Optional

from pydantic import BaseModel, Field

from shared.domain.decision import Decision
from write_api.agent.tools.registry import Tool


class DecisionArgs(Decision):
    node: Optional[str] = None  # filled from the situation if omitted
    sku: Optional[str] = None


class EscalateArgs(BaseModel):
    reason: str = Field(description="why the agent cannot decide safely on its own")
    findings: list[str] = Field(default_factory=list, description="key facts found, with numbers")
    questions_for_human: list[str] = Field(default_factory=list)


def _never_called(*_):  # pragma: no cover - the orchestrator handles terminal tools itself
    raise RuntimeError("terminal tools are handled by the orchestrator")


TOOLS = [
    Tool("submit_decision", "terminal",
         "Submit your final decision: type (accept | modify | reject | investigate | escalate), order lines for "
         "accept/modify, reasons that cite tool_call ids as evidence, risks, confidence and a plain summary. "
         "Code then validates it, asks a human if needed, places the orders and verifies the result.",
         DecisionArgs, _never_called),
    Tool("escalate", "terminal", "Hand the situation to a human buyer when no safe decision is possible.",
         EscalateArgs, _never_called),
]
