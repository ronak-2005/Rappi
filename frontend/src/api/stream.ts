// Live run trace via Server-Sent Events from the Read API (/runs/{id}/stream).
import { READ_API } from './client'
import type { RunDetail, TraceStep } from '../types/api'

export function streamRun(runId: string, onStep: (s: TraceStep) => void, onRun: (r: RunDetail) => void): () => void {
  const es = new EventSource(`${READ_API}/runs/${runId}/stream`)
  es.addEventListener('step', (e) => onStep(JSON.parse((e as MessageEvent).data)))
  es.addEventListener('run', (e) => {
    const run: RunDetail = JSON.parse((e as MessageEvent).data)
    onRun(run)
    if (run.finished) es.close()
  })
  es.onerror = () => es.close()
  return () => es.close()
}
