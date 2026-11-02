PY      := backend/.venv/bin/python
PIP     := backend/.venv/bin/pip

.PHONY: setup dev test lint smoke eval llm-check llm-models build-frontend clean

## Install backend (venv) and frontend (npm) dependencies; create env files if missing
setup:
	python3 -m venv backend/.venv
	$(PIP) install -q -e "backend[dev]"
	@test -f backend/.env || cp backend/.env.example backend/.env
	@test -f backend/llm.env || cp backend/llm.env.example backend/llm.env
	cd frontend && npm install

## Run read_api :8001, write_api :8002, mock_supplier :8003 and the frontend :5173
dev:
	./scripts/dev.sh

## Unit, API, agent (scripted LLM) and architecture tests — no API key needed
test:
	cd backend && .venv/bin/pytest -q

## Lint + format check: ruff (backend) and oxlint (frontend)
lint:
	cd backend && .venv/bin/ruff check . && .venv/bin/ruff format --check .
	cd frontend && npm run lint

## Start the real services, run one scenario with the no-key baseline, print the outcome
smoke:
	./scripts/smoke.sh

## Agent evaluation. Example: make eval LLM_ENVS="llm.env evals/llm/other.env" REPEATS=3
LLM_ENVS ?= llm.env
REPEATS  ?= 3
PAUSE    ?= 0
eval:
	cd backend && .venv/bin/python -m evals.run_evals --llm-envs $(LLM_ENVS) --repeats $(REPEATS) --pause $(PAUSE)

## Does this LLM env work and support tool calls?  make llm-check ENV=llm-examples/x.env
ENV ?= llm.env
llm-check:
	cd backend && .venv/bin/python -m evals.llm_check $(ENV)

## List the model ids an endpoint offers:  make llm-models ENV=llm-examples/gemini.env
llm-models:
	cd backend && .venv/bin/python -m evals.llm_check $(ENV) --models

build-frontend:
	cd frontend && npm run build

clean:
	rm -rf backend/var/*.db backend/var/logs backend/var/runs
