"""The orchestrator: a state machine that owns the agent loop. The LLM chooses tools and decisions;
this code decides what happens next and enforces the limits.

INTAKE → INVESTIGATE (LLM ⇄ tools, read side only)
  → submit_decision → EVIDENCE GATE → VALIDATE (rulebook)
       hard fail  → back to the LLM with the failures (max_revisions) → ESCALATED
       soft issue → AWAITING_APPROVAL (pause; a human approves / rejects / edits) → resume
       clean      → EXECUTE (gateway, idempotent) → VERIFY (re-projection with the supplier's real answer)
            OK / DEGRADED_OK → COMPLETED
            UNACCEPTABLE     → REPLAN: back to the LLM with the gap (max_replans) → ESCALATED
Limits: max tool calls, max format retries, max revisions, max replans (policy.yaml → loop_limits).
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from sqlmodel import Session

from shared.config.policy import Policy
from shared.db import models as m
from shared.db.session import read_write
from shared.domain.decision import Decision, ValidationReport
from shared.domain.planning import Option, PlanLine, TransferLine
from shared.observability.logging import run_id_var
from write_api.actions import approvals, gateway
from write_api.agent import evidence_gate
from write_api.agent.tools import ALL_TOOLS, BY_NAME, registry
from write_api.agent.tools.terminal.finish import DecisionArgs, EscalateArgs
from write_api.clients.read_api_client import ReadApiClient
from write_api.clients.supplier_client import SupplierClient
from write_api.llm.client import LLMClient, LLMResponse
from write_api.repositories import order_repository
from write_api.repositories import run_repository as runs
from write_api.validation.validator import validate
from write_api.verification import learning, verifier

log = logging.getLogger("write_api.agent.orchestrator")
PROMPTS = Path(__file__).parent / "prompts"
TOOL_RESULT_LIMIT = 12_000
REC_STATUS = {"accept": "accepted", "modify": "modified", "reject": "rejected", "investigate": "investigating",
              "escalate": "escalated"}

# An approver gets the approval (reasons + plan) and returns (decision, comment, edited_lines | None).
Approver = Callable[[dict], tuple[str, str, Optional[list[dict]]]]


def prompt(name: str, **kw) -> str:
    return (PROMPTS / f"{name}.md").read_text().format(**kw)


@dataclass
class AgentDeps:
    llm: LLMClient
    llm_mode: str
    read: ReadApiClient
    supplier: SupplierClient
    policy: Policy
    db_file: Optional[str] = None
    approver: Optional[Approver] = None
    trace_dir: Optional[Path] = None
    llm_env: Optional[str] = None  # remembered so a resumed run uses the same brain


@dataclass
class _Ctx:
    """Per-run working state (persisted to run.memory between pauses)."""
    run: m.AgentRun
    session: Session
    messages: list[dict] = field(default_factory=list)
    called: dict[str, str] = field(default_factory=dict)  # successful tool_call_id → tool name
    format_retries: int = 0
    pending: Optional[dict] = None
    executions: list[dict] = field(default_factory=list)
    verifications: list[dict] = field(default_factory=list)
    decisions: list[dict] = field(default_factory=list)


class Orchestrator:
    def __init__(self, deps: AgentDeps):
        self.d = deps
        self.limits = deps.policy.loop_limits
        self.tool_schemas = [t.schema() for t in ALL_TOOLS]

    # ------------------------------------------------------------------ public
    def start(self, trigger_ref: str, trigger_type: str = "recommendation") -> str:
        """Create a run for a trigger: a recommendation to review (S1/S4), a supplier event (S2) or a demand
        alert (S3). Returns the run id (call run() to execute)."""
        world = self.d.read.get("/world")
        if trigger_type == "recommendation":
            situation = self.d.read.get(f"/situation/recommendations/{trigger_ref}")
            rec = situation["recommendation"]
            node, sku, rec_id = rec["node"], rec["sku"], rec["id"]
            user = prompt("recommendation_review", qty=rec["qty"], sku=sku, node=node,
                          supplier_text=f" from supplier **{rec['supplier']}**" if rec.get("supplier") else "",
                          recommendation_id=rec_id, today=world["today"])
        elif trigger_type == "supplier_event":
            situation = self.d.read.get(f"/situation/supplier-events/{trigger_ref}")
            ev, po = situation["event"], situation["purchase_order"]
            node, sku, rec_id = ev["node"], ev["sku"], None
            user = prompt("supplier_shortfall", supplier=ev["supplier"], po_id=po["id"], qty_ordered=po["qty_ordered"],
                          qty_confirmed=po["qty_confirmed"], sku=sku, node=node, message=ev["message"],
                          today=world["today"])
        elif trigger_type == "demand_alert":
            situation = self.d.read.get(f"/situation/demand-alerts/{trigger_ref}")
            al = situation["alert"]
            node, sku, rec_id = al["node"], al["sku"], None
            user = prompt("demand_change", sku=sku, node=node, message=al["message"], today=world["today"])
        else:
            raise ValueError(f"unknown trigger type {trigger_type}")
        run_id = f"RUN-{datetime.now(timezone.utc):%Y%m%d%H%M%S}-{uuid.uuid4().hex[:4]}"
        memory = {"messages": [{"role": "system", "content": prompt("system")}, {"role": "user", "content": user}],
                  "called": {}, "format_retries": 0, "pending": None, "executions": [], "verifications": [],
                  "decisions": [], "node": node, "sku": sku, "recommendation_id": rec_id,
                  "trigger_type": trigger_type, "llm_env": self.d.llm_env,
                  "recommendation": situation.get("recommendation")}
        with read_write(self.d.db_file) as s:
            runs.create_run(s, id=run_id, fixture_id=world["fixture_id"], trigger_type=trigger_type,
                            trigger_ref=trigger_ref, status="running", state="INTAKE", llm_mode=self.d.llm_mode,
                            llm_model=getattr(self.d.llm, "model", ""), memory=memory)
            runs.add_step(s, run_id, "INTAKE", "info", "situation", situation)
        return run_id

    def run(self, run_id: str) -> m.AgentRun:
        """Run until the agent finishes, escalates, fails, or pauses for human approval."""
        run_id_var.set(run_id)
        with read_write(self.d.db_file) as s:
            c = self._load(s, run_id)
            try:
                self._loop(c)
            except Exception as exc:  # never leave a run half-way without a record
                log.exception("run %s crashed", run_id)
                self._step(c, "error", "crash", {"error": f"{type(exc).__name__}: {exc}"})
                self._finish(c, "failed", "FAILED", error=f"{type(exc).__name__}: {exc}")
            return runs.get_run(s, run_id)

    def resume(self, run_id: str) -> m.AgentRun:
        """Continue a run after its approval was resolved (approved / edited / rejected)."""
        run_id_var.set(run_id)
        with read_write(self.d.db_file) as s:
            c = self._load(s, run_id)
            try:
                if self._after_approval(c) == "continue":
                    self._loop(c)
            except Exception as exc:
                log.exception("run %s crashed on resume", run_id)
                self._step(c, "error", "crash", {"error": f"{type(exc).__name__}: {exc}"})
                self._finish(c, "failed", "FAILED", error=f"{type(exc).__name__}: {exc}")
            return runs.get_run(s, run_id)

    # ------------------------------------------------------------------ loop
    def _loop(self, c: _Ctx) -> None:
        self._set(c, status="running", state="INVESTIGATE")
        while True:
            if c.run.tool_calls >= self.limits.max_tool_calls:
                return self._escalate(c, f"tool-call budget of {self.limits.max_tool_calls} exhausted without a decision")
            resp = self._chat(c)
            c.messages.append(_assistant_message(resp))
            self._step(c, "llm_message", "assistant", {"text": resp.text, "tool_calls": [
                {"id": t.id, "name": t.name, "arguments": t.arguments} for t in resp.tool_calls]})
            if not resp.tool_calls:
                c.format_retries += 1
                if c.format_retries > self.limits.max_llm_format_retries:
                    return self._escalate(c, "the model stopped calling tools without submitting a decision")
                c.messages.append({"role": "user", "content": "Continue by calling a tool. "
                                   "Finish with submit_decision (or escalate)."})
                self._save(c)
                continue

            terminal = None
            for tc in resp.tool_calls:
                if tc.name in ("submit_decision", "escalate"):
                    if terminal is None:
                        terminal = tc
                    else:
                        self._tool_reply(c, tc.id, {"error": "only one decision per turn"})
                    continue
                self._run_tool(c, tc)
            if terminal is not None:
                outcome = self._terminal(c, terminal)
                if outcome != "continue":
                    return
            self._save(c)

    def _run_tool(self, c: _Ctx, tc) -> None:
        tool = BY_NAME.get(tc.name)
        c.run.tool_calls += 1
        if tool is None:
            self._tool_reply(c, tc.id, {"error": f"unknown tool '{tc.name}'",
                                        "available": [t.name for t in ALL_TOOLS]})
            return
        tctx = registry.ToolContext(read=self.d.read, db_file=self.d.db_file, policy=self.d.policy,
                                    node=c.run.memory["node"], sku=c.run.memory["sku"],
                                    recommendation_id=c.run.memory["recommendation_id"],
                                    trigger_type=c.run.memory.get("trigger_type", "recommendation"),
                                    trigger_ref=c.run.trigger_ref)
        out = registry.run(tool, tc.arguments, tctx)
        if out.ok:
            c.called[tc.id] = tc.name
        self._step(c, "tool_call", tc.name, {"id": tc.id, "arguments": tc.arguments, "ok": out.ok,
                                             "result": out.result})
        # the model can't see provider-assigned call ids, so each result carries its own id to cite as evidence
        self._tool_reply(c, tc.id, {"evidence_id": tc.id, **out.result})

    # ------------------------------------------------------------------ decisions
    def _terminal(self, c: _Ctx, tc) -> str:
        mem = c.run.memory
        if tc.name == "escalate":
            parsed, err = registry.parse_args(BY_NAME["escalate"], tc.arguments)
            if err:
                self._tool_reply(c, tc.id, err)
                return "continue"
            self._tool_reply(c, tc.id, {"status": "escalated to a human buyer"})
            e: EscalateArgs = parsed
            decision = {"type": "escalate", "summary": e.reason, "findings": e.findings,
                        "questions_for_human": e.questions_for_human}
            c.decisions.append(decision)
            return self._escalate(c, e.reason, decision)

        try:
            raw = json.loads(tc.arguments or "{}")
        except json.JSONDecodeError as exc:
            raw = None
            err = {"error": "arguments are not valid JSON", "detail": str(exc)}
        if raw is not None:
            raw.setdefault("node", mem["node"])
            raw.setdefault("sku", mem["sku"])
            raw.setdefault("recommendation_id", mem["recommendation_id"])
            parsed, err = registry.parse_args(BY_NAME["submit_decision"], json.dumps(raw))
        if err:
            c.format_retries += 1
            self._step(c, "gate", "decision_format", err)
            if c.format_retries > self.limits.max_llm_format_retries:
                self._tool_reply(c, tc.id, err)
                return self._escalate(c, "the model could not produce a valid decision form")
            self._tool_reply(c, tc.id, err)
            return "continue"

        decision = Decision.model_validate(parsed.model_dump())
        rec = mem.get("recommendation")
        if decision.type == "accept" and not decision.lines and not decision.transfers and rec:
            # "accept the recommendation" = place exactly what was recommended
            decision.lines = [PlanLine(supplier_id=rec["supplier"], qty=rec["qty"])]
        c.decisions.append(decision.model_dump())
        self._step(c, "decision", decision.type, decision.model_dump())

        gate = evidence_gate.check(decision, c.called, mem.get("trigger_type", "recommendation"))
        self._step(c, "gate", "evidence", gate or {"passed": True})
        if gate:
            c.run.revisions += 1
            self._tool_reply(c, tc.id, gate)
            if c.run.revisions > self.limits.max_revisions + 1:
                return self._escalate(c, "decision repeatedly failed the evidence gate")
            return "continue"

        if decision.type in ("investigate", "escalate"):
            self._tool_reply(c, tc.id, {"status": f"decision '{decision.type}' recorded; handed to a human buyer"})
            return self._finish(c, "escalated", "ESCALATED", decision=decision.model_dump())

        self._set(c, state="VALIDATE")
        report = validate(c.session, self.d.policy, decision.node, decision.sku, decision.lines,
                          decision.recommendation_id, decision.transfers, decision.demand_assumption)
        self._step(c, "validation", "rulebook", _report_payload(report))
        if not report.passed:
            c.run.revisions += 1
            failures = "\n".join(f"- {r.rule}: {r.message}" for r in report.hard_failures)
            self._tool_reply(c, tc.id, {"error": "rulebook rejected the plan", "hard_failures":
                                        [r.model_dump() for r in report.hard_failures],
                                        "instructions": prompt("rulebook_rejection", failures=failures)})
            if c.run.revisions > self.limits.max_revisions:
                return self._escalate(c, f"plan failed hard rules {c.run.revisions} times: {failures}")
            self._set(c, state="INVESTIGATE")
            return "continue"

        if report.requires_approval:
            self._tool_reply(c, tc.id, {"status": "valid, but needs human approval",
                                        "soft_violations": [r.model_dump() for r in report.soft_violations]})
            return self._request_approval(c, decision, report)

        acting = bool(decision.lines or decision.transfers)
        self._tool_reply(c, tc.id, {"status": "validated; executing" if acting else "validated; no action needed"})
        return self._act(c, decision, decision.lines, report.evaluation, decision.transfers)

    def _request_approval(self, c: _Ctx, decision: Decision, report: ValidationReport) -> str:
        reasons = [f"{r.rule}: {r.message}" for r in report.soft_violations]
        a = approvals.request(c.session, c.run.id, reasons, {
            "decision": decision.model_dump(), "lines": [ln.model_dump() for ln in decision.lines],
            "transfers": [t.model_dump() for t in decision.transfers],
            "evaluation": report.evaluation.model_dump() if report.evaluation else None})
        c.pending = {"approval_id": a.id}
        self._step(c, "approval", "requested", {"approval_id": a.id, "reasons": reasons})
        self._set(c, status="awaiting_approval", state="AWAITING_APPROVAL")
        if self.d.approver is None:
            self._save(c)
            return "pause"
        verdict, comment, edited = self.d.approver(a.model_dump())
        approvals.resolve(c.session, a.id, verdict, "auto-approver", comment, edited)
        return self._after_approval(c)

    def _after_approval(self, c: _Ctx) -> str:
        a = runs.get_approval(c.session, (c.pending or {}).get("approval_id", ""))
        if a is None or a.status == "pending":
            return "pause"
        self._step(c, "approval", a.status, {"approval_id": a.id, "by": a.resolved_by, "comment": a.comment})
        c.pending = None
        decision = Decision.model_validate(a.plan["decision"])
        if a.status == "rejected":
            note = f" Their comment: \"{a.comment}\"" if a.comment else ""
            c.messages.append({"role": "user", "content": prompt("approval_rejected", comment=note)})
            self._set(c, status="running", state="INVESTIGATE")
            return "continue"
        lines = [PlanLine.model_validate(x) for x in a.plan["lines"]]
        transfers = [TransferLine.model_validate(x) for x in a.plan.get("transfers", [])]
        expected = Option.model_validate(a.plan["evaluation"]) if a.plan.get("evaluation") else None
        if a.status == "edited":  # a human changed the plan: hard rules still apply
            report = validate(c.session, self.d.policy, decision.node, decision.sku, lines, decision.recommendation_id,
                              transfers, decision.demand_assumption)
            self._step(c, "validation", "rulebook_after_edit", _report_payload(report))
            if not report.passed:
                return self._escalate(c, "the human-edited plan breaks hard rules")
            expected = report.evaluation
        self._set(c, status="running")
        return self._act(c, decision, lines, expected, transfers)

    # ------------------------------------------------------------------ act + verify
    def _act(self, c: _Ctx, decision: Decision, lines: list[PlanLine], expected: Optional[Option],
             transfers: Optional[list[TransferLine]] = None) -> str:
        transfers = transfers or []
        if not lines and not transfers:  # validated reject / keep the current plan: nothing to execute
            return self._finish(c, "completed", "COMPLETED", decision=decision.model_dump())
        self._set(c, state="EXECUTE")
        result = gateway.execute(c.session, self.d.supplier, run_id=c.run.id, attempt_tag=f"plan-{c.run.replans}",
                                 node=decision.node, sku=decision.sku, lines=lines,
                                 recommendation_id=decision.recommendation_id, transfers=transfers)
        c.executions.append(result.model_dump())
        self._step(c, "action", "purchase_orders", result.model_dump())
        stats = learning.record(c.session, result)
        if stats:
            self._step(c, "info", "supplier_learning", {"updated": stats})

        self._set(c, state="VERIFY")
        report = verifier.verify(c.session, self.d.policy, node=decision.node, sku=decision.sku, expected=expected,
                                 execution=result, recommendation_id=decision.recommendation_id,
                                 demand=decision.demand_assumption)
        c.verifications.append(report.model_dump())
        self._step(c, "verification", report.status, report.model_dump())
        if report.status in ("OK", "DEGRADED_OK"):
            return self._finish(c, "completed", "COMPLETED", decision=decision.model_dump())

        c.run.replans += 1
        if c.run.replans > self.limits.max_replans:
            return self._escalate(c, f"verification still UNACCEPTABLE after {self.limits.max_replans} re-plans: "
                                     f"{report.message}")
        placed = ", ".join(f"{ln.po_id} ({ln.supplier_id}: {ln.qty_confirmed}/{ln.qty_requested}, {ln.status})"
                           for ln in result.lines)
        c.messages.append({"role": "user", "content": prompt(
            "replan", report=json.dumps(report.model_dump(), indent=1), placed=placed)})
        self._set(c, status="running", state="REPLAN")
        self._save(c)
        return "continue"

    # ------------------------------------------------------------------ endings
    def _escalate(self, c: _Ctx, reason: str, decision: Optional[dict] = None) -> str:
        self._step(c, "info", "escalated", {"reason": reason})
        return self._finish(c, "escalated", "ESCALATED",
                            decision=decision or {"type": "escalate", "summary": reason}, error=None)

    def _finish(self, c: _Ctx, status: str, state: str, decision: Optional[dict] = None,
                error: Optional[str] = None) -> str:
        self._save(c)
        final = decision or (c.decisions[-1] if c.decisions else None)
        outcome = {"executions": c.executions, "verifications": c.verifications, "decisions": c.decisions,
                   "final_verification": c.verifications[-1]["status"] if c.verifications else None}
        rec_id = c.run.memory.get("recommendation_id")
        if rec_id and final:
            order_repository.set_recommendation_status(c.session, rec_id, REC_STATUS.get(final.get("type"), "escalated"))
        self._set(c, status=status, state=state, decision=final, outcome=outcome,
                  finished_at=datetime.now(timezone.utc), error=error)
        self._step(c, "info", "finished", {"status": status, "decision_type": (final or {}).get("type")})
        return "done"

    # ------------------------------------------------------------------ plumbing
    def _chat(self, c: _Ctx) -> LLMResponse:
        resp = self.d.llm.chat(c.messages, self.tool_schemas)
        self._jsonl(c, "llm_calls", {"at": _now(), "messages": len(c.messages), "text": resp.text,
                                     "tool_calls": [t.__dict__ for t in resp.tool_calls], "usage": resp.usage})
        return resp

    def _tool_reply(self, c: _Ctx, call_id: str, result: dict) -> None:
        text = json.dumps(result, default=str)
        if len(text) > TOOL_RESULT_LIMIT:
            text = text[:TOOL_RESULT_LIMIT] + ' …"(truncated)"'
        c.messages.append({"role": "tool", "tool_call_id": call_id, "content": text})

    def _step(self, c: _Ctx, kind: str, name: str, payload: dict) -> None:
        payload = json.loads(json.dumps(payload, default=str))
        runs.add_step(c.session, c.run.id, c.run.state, kind, name, payload)
        self._jsonl(c, "trace", {"at": _now(), "state": c.run.state, "kind": kind, "name": name, "payload": payload})

    def _jsonl(self, c: _Ctx, name: str, row: dict) -> None:
        if self.d.trace_dir is None:
            return
        folder = self.d.trace_dir / c.run.id
        folder.mkdir(parents=True, exist_ok=True)
        with open(folder / f"{name}.jsonl", "a") as f:
            f.write(json.dumps(row, default=str) + "\n")

    def _set(self, c: _Ctx, **fields) -> None:
        c.run = runs.update_run(c.session, c.run, **fields)

    def _save(self, c: _Ctx) -> None:
        mem = dict(c.run.memory)
        mem.update(messages=c.messages, called=c.called, format_retries=c.format_retries, pending=c.pending,
                   executions=c.executions, verifications=c.verifications, decisions=c.decisions)
        self._set(c, memory=mem)

    def _load(self, s: Session, run_id: str) -> _Ctx:
        run = runs.get_run(s, run_id)
        mem = run.memory
        return _Ctx(run=run, session=s, messages=list(mem["messages"]), called=dict(mem["called"]),
                    format_retries=mem.get("format_retries", 0), pending=mem.get("pending"),
                    executions=list(mem.get("executions", [])), verifications=list(mem.get("verifications", [])),
                    decisions=list(mem.get("decisions", [])))


def _assistant_message(resp: LLMResponse) -> dict:
    msg: dict = {"role": "assistant", "content": resp.text or None}
    if resp.tool_calls:
        msg["tool_calls"] = [{"id": t.id, "type": "function", "function": {"name": t.name, "arguments": t.arguments}}
                             for t in resp.tool_calls]
    return msg


def _report_payload(r: ValidationReport) -> dict:
    return {"passed": r.passed, "requires_approval": r.requires_approval,
            "results": [x.model_dump() for x in r.all_results],
            "evaluation": {k: v for k, v in (r.evaluation.model_dump() if r.evaluation else {}).items()
                           if k in ("total_qty", "purchase_cost", "express_premium", "lost_units", "expired_units",
                                    "min_close", "end_close", "over_capacity_days", "below_ss_days")}}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")
