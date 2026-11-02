"""BaselineLLM: a deterministic, rule-based stand-in for the LLM (LLM_MODE=baseline).

It speaks the same interface as a real model and goes through the SAME orchestrator, tools,
evidence gate, rulebook, gateway and verifier. Its 'brain' is fixed:
  1. investigate a fixed list of facts for the trigger type
  2. high-severity data problem → investigate
  3. demand alert → adopt the engine's suggested demand assumption (if any)
  4. take the engine's best option → accept / modify / reject, or escalate if nothing is feasible
  5. project the chosen plan once, then submit

Why it exists: (1) the demo and tests run without an API key; (2) evals compare the LLM against it,
which shows where LLM judgment adds value (and where it doesn't).
"""

import json
from typing import Optional

from write_api.llm.client import LLMResponse, ToolCall

COMMON = ["get_inventory", "get_open_pos", "get_sales_history", "check_data_quality", "get_sku_profile",
          "get_supplier_terms", "get_budget", "get_storage_status"]
INVESTIGATION = {
    "recommendation_review": COMMON,
    "supplier_shortfall": COMMON + ["get_other_nodes_stock"],
    "demand_change": COMMON + ["get_promotions", "analyze_demand"],
}
REPLAN_MARK = "## Verification failed"


class BaselineLLM:
    model = "baseline-policy"

    def __init__(self):
        self.n = 0

    def chat(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        calls, results = _history(messages)
        last_user = max((i for i, m in enumerate(messages) if m["role"] == "user"), default=0)
        user_text = messages[last_user]["content"]

        if any(m["role"] == "tool" and '"rulebook rejected' in m["content"] for m in messages[-2:]) \
                or ("REJECTED your plan" in user_text and last_user == len(messages) - 1):
            return self._call("escalate", {"reason": "The plan was rejected (rulebook or human) and the baseline "
                                                     "policy has no alternative strategy.",
                                           "questions_for_human": ["Which alternative should be used?"]})

        ids = _latest_ids(calls, results)
        if "get_situation" not in ids:
            return self._call("get_situation", {})
        kind = results[ids["get_situation"]].get("type", "recommendation_review")
        for name in INVESTIGATION[kind]:
            if name not in ids:
                return self._call(name, {})

        demand = self._demand(results.get(ids.get("analyze_demand"), {}))
        replanning = user_text.startswith(REPLAN_MARK)
        since = last_user if replanning else 0
        fresh = {c["name"] for c in calls if c["index"] > since}
        for name in ("compute_requirement", "generate_options"):
            if name not in fresh:
                return self._call(name, demand or {})

        decision = self._decide(kind, ids, results, replanning, demand)
        if decision["type"] in ("accept", "modify", "reject"):  # look before you leap
            opts_at = max(c["index"] for c in calls if c["name"] == "generate_options")
            if not any(c["name"] == "project_inventory" and c["index"] > opts_at for c in calls):
                return self._call("project_inventory", {"lines": decision.get("lines", []),
                                                        "transfers": decision.get("transfers", []), **(demand or {})})
            proj = results.get(ids.get("project_inventory"), {}).get("summary", {})
            decision["reasons"].append({"factor": "projection", "finding": (
                f"with this plan: lost {proj.get('lost_units')}, expired {proj.get('expired_units')}, "
                f"min stock {proj.get('min_close')}, end stock {proj.get('end_close')}"),
                "evidence": [ids["project_inventory"]]})
        return self._call("submit_decision", decision)

    # ------------------------------------------------------------------
    @staticmethod
    def _demand(signal: dict) -> Optional[dict]:
        s = signal.get("suggested_assumption")
        return {"demand_per_day": s["per_day"], "demand_until_day": s.get("until_day")} if s else None

    def _decide(self, kind: str, ids: dict, results: dict, replanning: bool, demand: Optional[dict]) -> dict:
        r = lambda name: results.get(ids.get(name), {})  # noqa: E731
        ev = lambda *names: [ids[n] for n in names if n in ids]  # noqa: E731
        sit = r("get_situation").get("recommendation") or {}
        req, opts, dq = r("compute_requirement"), r("generate_options").get("options", []), r("check_data_quality")
        extra: dict = {}
        if demand:
            extra["demand_assumption"] = {"per_day": demand["demand_per_day"], "until_day": demand["demand_until_day"],
                                          "reason": r("analyze_demand").get("explanation", "")}

        high = [a for a in dq.get("anomalies", []) if a["severity"] == "high"]
        if high and not replanning:
            return {"type": "investigate", "confidence": "high",
                    "reasons": [{"factor": a["code"], "finding": a["message"],
                                 "evidence": ev("check_data_quality", "get_inventory")} for a in high],
                    "summary": "Stock data is unreliable; verify the physical stock before buying.",
                    "questions_for_human": ["Please run a cycle count for this SKU at this store."]}

        demand_reason = ([{"factor": "demand", "finding": r("analyze_demand").get("explanation", ""),
                           "evidence": ev("analyze_demand", "get_sales_history", "get_promotions")}]
                         if kind == "demand_change" else [])
        best = opts[0] if opts else None
        buyable = [o for o in opts if o["hard_rules_ok"] and (o["lines"] or o["transfers"])]
        if best and best["kind"] == "do_nothing" and not best["soft_issues_needing_approval"]:
            no_need = {"factor": "no_need", "finding": req.get("formula", "requirement ≤ 0"),
                       "evidence": ev("compute_requirement", "get_open_pos", "get_inventory")}
            if kind == "recommendation_review":
                return {"type": "reject", "confidence": "high", "reasons": [no_need],
                        "summary": "Current stock plus open orders already cover the horizon; no purchase needed."}
            return {"type": "accept", "confidence": "high", "reasons": demand_reason + [no_need], **extra,
                    "summary": "Stock plus what is still coming covers the protection interval; no further action."}
        if not buyable:
            failed = {o["option_id"]: o["failed_hard_checks"] for o in opts if o["lines"] or o["transfers"]}
            return {"type": "escalate", "confidence": "high",
                    "reasons": [{"factor": "no_feasible_option",
                                 "finding": f"no buying or transfer option passes the hard rules: {failed or 'none available'}",
                                 "evidence": ev("generate_options", "get_supplier_terms", "get_other_nodes_stock")}],
                    "summary": "No feasible plan; a human must decide (e.g. MOQ exception, accept waste, emergency supplier).",
                    "questions_for_human": ["Which exception or alternative source should be used?"]}

        clean = [o for o in buyable if not o["soft_issues_needing_approval"]]
        pick = (clean or buyable)[0]
        lines = [{k: v for k, v in ln.items() if v is not None} for ln in pick["lines"]]
        same = (kind == "recommendation_review" and not replanning and sit and not pick["transfers"]
                and len(lines) == 1 and lines[0]["supplier_id"] == sit.get("supplier")
                and lines[0].get("mode", "standard") == "standard" and "delivery_day" not in lines[0]
                and abs(lines[0]["qty"] - sit["qty"]) <= 0.05 * sit["qty"])
        reasons = demand_reason + [
            {"factor": "requirement", "finding": req.get("formula", ""),
             "evidence": ev("compute_requirement", "get_inventory", "get_open_pos")},
            {"factor": "best_option", "finding": f"{pick['label']}: decision cost {pick['decision_cost']}, "
                                                 f"lost {pick['lost_units']}, expired {pick['expired_units']}",
             "evidence": ev("generate_options")}]
        if pick["soft_issues_needing_approval"]:
            reasons.append({"factor": "needs_approval", "finding": f"soft issues: {pick['soft_issues_needing_approval']}",
                            "evidence": ev("generate_options", "get_budget")})
        return {"type": "accept" if same else "modify", "lines": lines, "transfers": pick["transfers"],
                "option_id": pick["option_id"], "confidence": "medium", "reasons": reasons, **extra,
                "risks": [f"soft issue: {s}" for s in pick["soft_issues_needing_approval"]],
                "summary": f"{'Accept' if same else 'Modify'}: {pick['label']}."}

    def _call(self, name: str, args: dict) -> LLMResponse:
        self.n += 1
        return LLMResponse(tool_calls=[ToolCall(id=f"bl_{self.n:02d}_{name}", name=name, arguments=json.dumps(args))])


def _history(messages: list[dict]) -> tuple[list[dict], dict[str, dict]]:
    calls, results = [], {}
    for i, m in enumerate(messages):
        if m["role"] == "assistant":
            for tc in m.get("tool_calls") or []:
                calls.append({"id": tc["id"], "name": tc["function"]["name"], "index": i})
        elif m["role"] == "tool":
            results[m["tool_call_id"]] = _json(m["content"])
    return calls, results


def _latest_ids(calls: list[dict], results: dict) -> dict[str, str]:
    ids = {}
    for c in calls:  # latest successful id per tool
        if c["id"] in results and "error" not in results[c["id"]]:
            ids[c["name"]] = c["id"]
    return ids


def _json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"error": "unparseable"}
