#!/usr/bin/env bash
# Start every process for local development. Ctrl+C stops them all.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT/backend"
mkdir -p var/logs

UVICORN=".venv/bin/uvicorn"
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

$UVICORN mock_supplier.server.main:app --port 8003 --reload & pids+=($!)
$UVICORN read_api.server.main:app      --port 8001 --reload & pids+=($!)
$UVICORN write_api.server.main:app     --port 8002 --reload & pids+=($!)
(cd "$ROOT/frontend" && npm run dev -- --port 5173) & pids+=($!)

echo "read_api :8001 | write_api :8002 | mock_supplier :8003 | frontend http://localhost:5173"
wait
