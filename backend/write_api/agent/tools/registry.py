"""Tool registry: name → description → argument model (Pydantic) → handler.

Arguments produced by the LLM are NEVER trusted: they are parsed and validated here, and a clear
error (with what to fix) goes back to the model instead of crashing the run. JSON schemas sent to
the model are fully inlined (no $ref) because providers differ in what they accept.
"""

import json
from dataclasses import dataclass
from typing import Any, Callable, Literal, Optional

from pydantic import BaseModel, ValidationError

from shared.config.policy import Policy
from write_api.clients.read_api_client import ReadApiClient


@dataclass
class ToolContext:
    read: ReadApiClient
    db_file: Optional[str]
    policy: Policy
    node: str
    sku: str
    recommendation_id: Optional[str]
    trigger_type: str = "recommendation"
    trigger_ref: str = ""


@dataclass
class Tool:
    name: str
    kind: Literal["read", "compute", "terminal"]
    description: str
    args_model: type[BaseModel]
    handler: Callable[[Any, ToolContext], dict]

    def schema(self) -> dict:
        return {"type": "function", "function": {
            "name": self.name, "description": self.description,
            "parameters": inline_refs(self.args_model.model_json_schema())}}


def inline_refs(schema: dict) -> dict:
    defs = schema.pop("$defs", {})

    def resolve(node):
        if isinstance(node, dict):
            if "$ref" in node:
                return resolve(dict(defs[node["$ref"].split("/")[-1]]))
            return {k: resolve(v) for k, v in node.items() if k != "title"}
        if isinstance(node, list):
            return [resolve(x) for x in node]
        return node

    return resolve(schema)


@dataclass
class ToolOutcome:
    ok: bool
    result: dict
    parsed: Optional[BaseModel] = None


def parse_args(tool: Tool, raw: str) -> tuple[Optional[BaseModel], Optional[dict]]:
    try:
        data = json.loads(raw) if raw and raw.strip() else {}
    except json.JSONDecodeError as exc:
        return None, {"error": "arguments are not valid JSON", "detail": str(exc),
                      "fix": "call the tool again with a single valid JSON object"}
    try:
        return tool.args_model.model_validate(data), None
    except ValidationError as exc:
        return None, {"error": "arguments do not match the tool schema",
                      "problems": [{"field": ".".join(map(str, e["loc"])), "issue": e["msg"]} for e in exc.errors()],
                      "fix": "correct these fields and call the tool again"}


def run(tool: Tool, raw_args: str, ctx: ToolContext) -> ToolOutcome:
    parsed, error = parse_args(tool, raw_args)
    if error:
        return ToolOutcome(False, error)
    try:
        return ToolOutcome(True, tool.handler(parsed, ctx), parsed)
    except Exception as exc:  # a failing tool must not kill the run: the model sees the error
        return ToolOutcome(False, {"error": f"{type(exc).__name__}: {exc}"})
