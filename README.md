# AI Purchasing Agent

An agent that reviews purchasing situations for a quick-commerce business (dark stores), investigates the facts, decides, **executes**, and **verifies its own action**. It is not a chatbot that answers purchasing questions.

> 🚧 Work in progress. See [CHECKPOINTS.md](CHECKPOINTS.md) for what works at each tagged push.

## Core idea in one paragraph
Maths and rules are deterministic code. The LLM does the judgment: what to investigate, what the evidence means, which feasible option to choose, and how to explain it. The backend is split into a **Read API** (read-only database connection: the agent investigates through it and *cannot* change anything) and a **Write API** (the only service that changes state; every change passes the rulebook, the approval gate and duplicate-order protection, then gets verified).

## Repository layout
```
backend/
  shared/         stateless: config, DB schema, domain types, pure maths (engine), logging
  read_api/       READ side   : server/ controllers/ services/ repositories/ schemas/   (:8001)
  write_api/      WRITE side  : server/ controllers/ services/ repositories/ schemas/   (:8002)
                  + agent/ llm/ validation/ actions/ verification/ clients/
  mock_supplier/  simulated external supplier system                                    (:8003)
  fixtures/       scenario worlds + expected outcomes (YAML)
  tests/  evals/
frontend/         static React + Vite app                                               (:5173)
docs/             architecture, structure/debug map, decisions, evaluation
```
See [docs/structure.md](docs/structure.md) for what each folder does and where to look when debugging.

## Setup
Requirements: Python 3.12+, Node 20+.
```bash
make setup        # venv + npm install; creates backend/.env and backend/llm.env from the examples
```

### LLM configuration (`backend/llm.env`)
Only generic fields; any OpenAI-compatible endpoint works without code changes:
```env
LLM_BASE_URL=https://api.anthropic.com/v1/
LLM_API_KEY=...
LLM_MODEL=claude-sonnet-5-5
```
No key? Set `LLM_MODE=baseline` (deterministic policy, no LLM) or `LLM_MODE=scripted`.

## Run
```bash
make dev          # read_api :8001, write_api :8002, mock_supplier :8003, UI http://localhost:5173
make test         # all tests, no API key needed
make eval         # agent evaluation report → backend/evals/reports/
```

## Documentation
- Architecture & approach: [docs/architecture.md](docs/architecture.md) *(coming)*
- Folder map & debugging: [docs/structure.md](docs/structure.md)
- Evaluation & validation: [docs/evaluation.md](docs/evaluation.md) *(coming)*
