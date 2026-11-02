# Structure: the path tells you the job

## Services
| Service | Port | Role | Can change data? |
|---|---|---|---|
| `backend/read_api` | 8001 | Every query: facts, projections, options, run traces | **No**: DB opened read-only |
| `backend/write_api` | 8002 | Every command: load scenario, run agent, approvals, POs; hosts the agent | Yes, the only one |
| `backend/mock_supplier` | 8003 | Simulated external supplier (confirm / partial / reject / delay / timeout) | Its own state only |
| `frontend` | 5173 | Static React UI | No (calls the APIs) |

Each API has the same internal layout:
```
server/        process boot, middleware, error handlers, health
controllers/   HTTP handlers, thin: parse → call service → return schema
services/      use-case / query logic
repositories/  database access (read side: SELECT only; write side: INSERT/UPDATE)
schemas/       request/response models
```

## Boundary rules (enforced by `backend/tests/architecture/test_imports.py`)
- `read_api` never imports `write_api`, and vice versa. They talk only over HTTP.
- Both may import `shared`; `shared` imports neither.
- `shared/engine` does no I/O (no DB, HTTP or LLM).
- Only `write_api/actions` creates or changes purchase orders and transfers.
- Only `write_api/llm` talks to an LLM.

## Debug map
| Symptom | Look here first |
|---|---|
| A server won't start / 500 errors | `<side>/server/`, `shared/config/`, `backend/var/logs/<service>.log` |
| Wrong numbers shown or used | `shared/engine/` (+ `tests/shared/engine/`), then `read_api/services/` |
| Wrong data returned | `read_api/repositories/` |
| Plan rejected / allowed unexpectedly | `write_api/validation/rules/hard|soft/` (one rule per file) |
| Order duplicated or missing | `write_api/actions/gateway.py`, `write_api/repositories/` |
| Agent skipped a check / odd choice | `backend/var/runs/<run_id>/trace.jsonl`, `write_api/agent/prompts/`, `write_api/agent/evidence_gate.py` |
| LLM errors / bad tool calls | `backend/var/runs/<run_id>/llm_calls.jsonl`, `write_api/llm/`, `GET :8002/health/llm` |
| Supplier behaves oddly | `mock_supplier/behaviours.py`, the fixture YAML |
| UI shows wrong data | `frontend/src/api/read.ts` or `write.ts` → the matching controller |

Every log line and error response carries `service`, `component` (folder) and `run_id`.
