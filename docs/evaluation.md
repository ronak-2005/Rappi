# Evaluation: how we know the agent's decisions are right

## 1. Ground truth that doesn't come from the agent
Every scenario is a YAML fixture (`backend/fixtures/`) with a complete world (stock, forecasts, sales,
open POs, suppliers, budgets, storage, promotions, other stores), a trigger, injected supplier
behaviour, and an **expected outcome computed by hand**. The arithmetic is written in each fixture's
`notes`, so a reviewer can check it with a calculator.

The engine is then tested **against those hand calculations** (`tests/shared/engine/test_fixture_answers.py`,
`tests/write_api/test_s2_s3_answers.py`). Hand and code were written independently, and the tests caught
mistakes on both sides:
- the engine found that the 800-unit recommendation would also let 100 units expire (missed by hand);
- the first hand-sized express bridge only kept stock ≥ 0, not ≥ safety stock (fixed in the fixture);
- the first forecast-override rule ignored the 3-day level, wrongly asking for approval on a promotion.

## 2. Scenarios
| Scenario | Fixtures | What they probe |
|---|---|---|
| S1 recommendation review | accept · modify (open PO ignored) · reject (overstock) · investigate (phantom stock) · modify (MOQ vs shelf life → other supplier) | Is the recommendation trusted blindly? Does the agent stop on bad data? |
| S2 supplier shortfall | sufficient anyway · transfer from another store · second supplier · second supplier also refuses | Does it check whether the gap matters, use other stores, and escalate when stuck? |
| S3 demand change | sustained increase · promotion ending today · one-day spike | Does it separate real change from noise, and plan on evidenced demand? |
| S4 constraints | storage on delivery day (two drops) · budget (approval) · express bridge · MOQ vs shelf life (no feasible plan) · partial confirmation (re-plan) · timeout (idempotency) | Constraints, human approval, and what happens when the first action doesn't work |

## 3. Graders: code, not opinion
`backend/evals/graders.py` turns the assignment's questions into independent checks:

| Assignment question | Checks |
|---|---|
| Was the decision correct? | `decision_type`, `quantity` (a range, not one number), `order_lines`, `supplier`, `transfers`, `transfer_quantity`, `demand_assumption` |
| Did it obtain the necessary information? | `required_evidence` (tools that must have been called successfully), `evidence_gate_first_try` (did it cite real evidence without being told) |
| Did it respect relevant constraints? | `validated_before_acting` (no action without a passing rulebook), `approval_gate` (a human was asked exactly when expected) |
| Did it take the appropriate action? | `purchase_orders` (count), `no_duplicate_orders` (our side and the supplier's side), `supplier_side_orders` |
| Did it validate the result? | `verified_after_acting`, `final_verification` (OK / DEGRADED_OK / UNACCEPTABLE as expected) |
| What happens when the initial action does not work? | `recovered_by_replanning` (+ `replan_quantity`), `escalated`, `run_finished_cleanly` |

A run **passes** only if every applicable check passes. The report shows per-check pass rates too,
so "right decision, sloppy evidence" is visible rather than hidden in a single score.

## 4. Repeats and comparison
- LLM output varies, so LLM runs are repeated (`REPEATS`) and reported as **pass rates**.
- The deterministic **baseline brain** runs through the *same* orchestrator, tools, rules and verifier.
  It is the reference point: where the LLM scores below it, the LLM is adding risk; where it scores
  equal, the deterministic core is doing the work; where the LLM explains better or handles cases the
  baseline can't, that is the LLM's value.
- Each LLM is just an env file (`LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`), so comparing models needs
  no code change: `make eval LLM_ENVS="a.env b.env" REPEATS=3`.

## 5. Beyond the graders
- **Scripted-LLM tests** (`tests/write_api/test_orchestrator_paths.py`) drive the orchestrator through
  misbehaviour on purpose: invalid JSON, schema errors, invented evidence ids, skipped checks, a plan
  the rulebook rejects, a model that stops calling tools, tool budget exhaustion, unknown tools, human
  approve / edit (edit breaking a hard rule) / reject.
- **Smoke test with real processes** (`make smoke`): the full S4 partial-confirmation loop across
  four processes over HTTP.

## 6. Results
See [`backend/evals/reports/report.md`](../backend/evals/reports/report.md) (also on the UI's Evaluation
page). The findings from the live runs are summarised below.

### Baseline brain (deterministic, no LLM)
18 / 18 scenarios pass every check.

### Live LLM: `nvidia/nemotron-3-ultra-550b-a55b:free` via OpenRouter (2026-11-02)
Only partly measured: the free tier allows about 50 requests per day without credits, and one scenario
takes about 15 requests.

| Scenario | Result | Notes |
|---|---|---|
| `s1_modify_open_po_ignored` (run 1) | decision right (MODIFY 500, verified OK) but **failed `evidence_gate_first_try`** | Our bug, not the model's: providers assign tool-call ids the model never sees, so it invented `call_1…`. The gate rejected that with the list of real ids and the model corrected itself. Fix: every tool result now carries its own `evidence_id`. |
| `s1_modify_open_po_ignored` (run 2) | **PASS** | All checks, 70 s |
| `s1_accept` | **PASS** | |
| `s1_investigate_phantom_stock` | **PASS** | stopped on bad stock data instead of buying |
| `s1_modify_moq_vs_shelf_life` | **PASS** | switched supplier to avoid expiry |
| remaining 14 | not run | daily quota reached; runs that hit provider errors are reported as `infra_error` and **not** counted as agent failures |

Lessons so far:
1. Grounding needs the ids to be visible to the model; the evidence gate caught the problem on the
   first live run.
2. Provider rate limits must be separated from agent mistakes in the report (the first report counted
   them as failures; fixed).

