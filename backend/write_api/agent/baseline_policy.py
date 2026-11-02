"""BaselineLLM: a deterministic, rule-based stand-in for the LLM (LLM_MODE=baseline).

It speaks the same interface as a real model and goes through the SAME orchestrator, tools,
evidence gate, rulebook, gateway and verifier. Its 'brain' is fixed:
  investigate the standard facts → if data quality has a high-severity flag, investigate →
  take the engine's best option → accept / modify / reject, or escalate if nothing is feasible.

Why it exists: (1) the demo and tests run without an API key; (2) evals compare the LLM against it,
which shows where LLM judgment adds value (and where it doesn't).
"""

import json
from typing import Optional

from write_api.llm.client import LLMResponse, ToolCall

INVESTIGATION = ["get_situation", "get_inventory", "get_open_pos", "get_sales_history", "check_data_quality",
                 "get_sku_profile",
                 "get_supplier_terms", "get_budget", "get_storage_status", "compute_requirement", "generate_options"]
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
                or "REJECTED your plan" in user_text and last_user == len(messages) - 1:
            return self._call("escalate", {"reason": "The plan was rejected (rulebook or human) and the baseline "
                                                     "policy has no alternative strategy.",
                                           "questions_for_human": ["Which alternative should be used?"]})

        replanning = user_text.startswith(REPLAN_MARK)
        if replanning:
            fresh = {c["name"] for c in calls if c["index"] > last_user}
            for name in ("compute_requirement", "generate_options"):
                if name not in fresh:
                    return self._call(name, {})
        else:
            done = {c["name"] for c in calls}
            for name in INVESTIGATION:
                if name not in done:
                    return self._call(name, {})

        ids = {}
        for c in calls:  # latest successful id per tool
            if c["id"] in results and "error" not in results[c["id"]]:
                ids[c["name"]] = c["id"]
        decision = self._decide(ids, results, replanning)
        if decision.get("lines"):  # look before you leap: project the chosen plan once before submitting
            opts_at = max(c["index"] for c in calls if c["name"] == "generate_options")
            if not any(c["name"] == "project_inventory" and c["index"] > opts_at for c in calls):
                return self._call("project_inventory", {"lines": decision["lines"]})
            proj = results.get(ids.get("project_inventory"), {}).get("summary", {})
            decision["reasons"].append({"factor": "projection", "finding": (
                f"with this plan: lost {proj.get('lost_units')}, expired {proj.get('expired_units')}, "
                f"min stock {proj.get('min_close')}, end stock {proj.get('end_close')}"),
                "evidence": [ids["project_inventory"]]})
        return self._call("submit_decision", decision)

    # ------------------------------------------------------------------
    def _decide(self, ids: dict, results: dict, replanning: bool) -> dict:
        r = lambda name: results.get(ids.get(name), {})  # noqa: E731
        sit = r("get_situation").get("recommendation", {})
        req, opts, dq = r("compute_requirement"), r("generate_options").get("options", []), r("check_data_quality")
        ev = lambda *names: [ids[n] for n in names if n in ids]  # noqa: E731

        high = [a for a in dq.get("anomalies", []) if a["severity"] == "high"]
        if high and not replanning:
            return {"type": "investigate", "confidence": "high",
                    "reasons": [{"factor": a["code"], "finding": a["message"],
                                 "evidence": ev("check_data_quality", "get_inventory")} for a in high],
                    "summary": "Stock data is unreliable; verify the physical stock before buying.",
                    "questions_for_human": ["Please run a cycle count for this SKU at this store."]}

        best = opts[0] if opts else None
        buyable = [o for o in opts if o["hard_rules_ok"] and o["lines"]]
        if best and best["kind"] == "do_nothing" and not best["soft_issues_needing_approval"]:
            return {"type": "reject", "confidence": "high",
                    "reasons": [{"factor": "no_need", "finding": req.get("formula", "requirement ≤ 0"),
                                 "evidence": ev("compute_requirement", "get_open_pos", "get_inventory")}],
                    "summary": "Current stock plus open orders already cover the horizon; no purchase needed."}
        if not buyable:
            failed = {o["option_id"]: o["failed_hard_checks"] for o in opts if o["lines"]}
            return {"type": "escalate", "confidence": "high",
                    "reasons": [{"factor": "no_feasible_option", "finding": f"every buying option fails hard rules: {failed}",
                                 "evidence": ev("generate_options", "get_supplier_terms")}],
                    "summary": "No plan satisfies the hard rules; a human must choose (e.g. MOQ exception or accept waste).",
                    "questions_for_human": ["Can the supplier waive the MOQ, or should we accept the projected waste?"]}

        clean = [o for o in buyable if not o["soft_issues_needing_approval"]]
        pick = (clean or buyable)[0]
        lines = [{k: v for k, v in ln.items() if v is not None} for ln in pick["lines"]]
        same = (not replanning and sit and len(lines) == 1 and lines[0]["supplier_id"] == sit.get("supplier")
                and lines[0].get("mode", "standard") == "standard" and "delivery_day" not in lines[0]
                and abs(lines[0]["qty"] - sit["qty"]) <= 0.05 * sit["qty"])
        reasons = [{"factor": "requirement", "finding": req.get("formula", ""),
                    "evidence": ev("compute_requirement", "get_inventory", "get_open_pos")},
                   {"factor": "best_option", "finding": f"{pick['label']}: decision cost {pick['decision_cost']}, "
                                                        f"lost {pick['lost_units']}, expired {pick['expired_units']}",
                    "evidence": ev("generate_options")}]
        if pick["soft_issues_needing_approval"]:
            reasons.append({"factor": "needs_approval", "finding": f"soft issues: {pick['soft_issues_needing_approval']}",
                            "evidence": ev("generate_options", "get_budget")})
        return {"type": "accept" if same else "modify", "lines": lines, "option_id": pick["option_id"],
                "confidence": "medium", "reasons": reasons,
                "risks": [f"soft issue: {s}" for s in pick["soft_issues_needing_approval"]],
                "summary": f"{'Accept' if same else 'Modify to'}: {pick['label']}."}

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


def _json(text: str) -> Optional[dict]:
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return {"error": "unparseable"}
