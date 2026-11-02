#!/usr/bin/env bash
# Smoke test with the REAL processes on their ports: start the 3 backend services, run one scenario
# with the no-key baseline brain, check the outcome, stop everything.
# Usage: scripts/smoke.sh [fixture_id]   (default: s4_feedback_partial_confirm)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FIXTURE="${1:-s4_feedback_partial_confirm}"
cd "$ROOT/backend"
LOGS="var/logs"; mkdir -p "$LOGS"
UV=".venv/bin/uvicorn"
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; }
trap cleanup EXIT

$UV mock_supplier.server.main:app --port 8003 >"$LOGS/smoke_supplier.out" 2>&1 & pids+=($!)
$UV read_api.server.main:app      --port 8001 >"$LOGS/smoke_read.out" 2>&1 & pids+=($!)
$UV write_api.server.main:app     --port 8002 >"$LOGS/smoke_write.out" 2>&1 & pids+=($!)

wait_for() { curl -sf --retry 30 --retry-connrefused --retry-delay 1 "$1" >/dev/null; }
wait_for localhost:8003/health && wait_for localhost:8001/docs && wait_for localhost:8002/health
echo "✓ services up"

RUN=$(curl -sf -X POST localhost:8002/runs -H 'content-type: application/json' \
      -d "{\"fixture_id\":\"$FIXTURE\",\"llm_mode\":\"baseline\"}")
RID=$(python3 -c "import sys,json;print(json.loads(sys.argv[1])['run_id'])" "$RUN")
echo "▶ run $RID ($FIXTURE)"

for _ in $(seq 1 60); do
  STATUS=$(curl -sf "localhost:8001/runs/$RID" | python3 -c "import sys,json;print(json.load(sys.stdin)['status'])")
  [ "$STATUS" != "running" ] && break
  curl -s --max-time 1 localhost:9/ >/dev/null 2>&1 || true   # ~1s pause without sleep
done

curl -sf "localhost:8001/runs/$RID" | python3 -c "
import sys, json
d = json.load(sys.stdin)
print('status:', d['status'], '| replans:', d['replans'], '| final verification:', (d['outcome'] or {}).get('final_verification'))
for p in d['purchase_orders']:
    print('  PO', p['id'], p['supplier_id'], 'ordered', p['qty_ordered'], 'confirmed', p['qty_confirmed'], p['status'])
"
echo "supplier-side orders: $(curl -sf localhost:8003/orders | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')"
echo "SSE first event:"; timeout 3 curl -sN "localhost:8001/runs/$RID/stream" | head -c 300 || true; echo
echo "trace file: backend/var/runs/$RID/trace.jsonl ($(wc -l < "var/runs/$RID/trace.jsonl") lines)"
