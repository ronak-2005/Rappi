# Checkpoints

Every push is tagged `checkpoint-NN-<name>`. Check one out with `git checkout checkpoint-NN-<name>`.

| Tag | What works at this point |
|---|---|
| `checkpoint-00-scaffold` | Repo layout (backend read/write split + frontend), env examples, Makefile, import-boundary tests |
| `checkpoint-01-data-model` | DB schema, read-only vs read-write sessions (writes rejected on the read side), policy.yaml, fixture format + loader, 11 S1/S4 fixtures with hand-computed expected outcomes |
| `checkpoint-02-engine` | Pure planning engine: calendar, safety stock, day-by-day FEFO projection (expiry + storage), net requirement, option generator (standard / express / bridge / two drops / within budget / waste-free) with decision cost and per-rule checks, data-quality flags. Engine reproduces every fixture's hand-computed answer |
| `checkpoint-02.1-engine-fix` | ⚠️ `checkpoint-02-engine` was pushed with 1 failing test (phantom-stock rule flagged stores that genuinely sold out days ago). Fixed here: the rule only fires when the product sold *yesterday* while the system shows 0. From now on every checkpoint goes through `scripts/checkpoint.sh`, which refuses to commit unless all tests pass |
| `checkpoint-03-read-api` | Read API (:8001) — read-only DB session; facts (inventory, open POs, sales, forecast, promotions, suppliers, budget, storage), planning queries (requirement, projection, options, evaluate plan, data quality), runs/trace/SSE, fixtures catalogue; JSON errors with service + component. docs/decisions.md |
| `checkpoint-04-act-and-verify` | Mock supplier (:8003, injectable confirm/partial/reject/delay/timeout), rulebook (6 hard + 7 soft rules, one file each), gateway with idempotency keys + retry (no duplicate on timeout), verifier (OK / DEGRADED_OK / UNACCEPTABLE + residual need), supplier learning loop |
| `checkpoint-05-agent` | The agent: generic OpenAI-compatible LLM client (llm.env: base URL / key / model only), 19 tools (12 look-up via Read API, 5 calculate, 2 finish), prompts as .md files, evidence gate, orchestrator state machine (validate → approve → execute → verify → re-plan/escalate, with limits), no-key baseline brain, Write API (:8002) with background runs + approvals + LLM health. All 11 S1/S4 fixtures pass every grader end-to-end; scripted-LLM tests for misbehaving models; `make smoke` runs the real processes |
