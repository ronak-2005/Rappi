// Keeps a run's trace + detail up to date: SSE for live steps, plus a refetch after each run event.
// The run page is keyed by run id, so a new run gets fresh state (no reset needed here).
import { useCallback, useEffect, useState } from 'react'
import { readApi } from '../api/read'
import { streamRun } from '../api/stream'
import type { RunDetail, TraceStep } from '../types/api'

export function useRunStream(runId: string) {
  const [steps, setSteps] = useState<TraceStep[]>([])
  const [run, setRun] = useState<RunDetail | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const [r, t] = await Promise.all([readApi.run(runId), readApi.trace(runId)])
      setRun(r)
      setSteps(t)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [runId])

  useEffect(() => {
    // oxlint-disable-next-line react/set-state-in-effect -- network fetch: state is set when the request resolves
    refresh()
    const stop = streamRun(
      runId,
      (s) => setSteps((prev) => (prev.some((p) => p.seq === s.seq) ? prev : [...prev, s].sort((a, b) => a.seq - b.seq))),
      (r) => setRun(r),
    )
    return stop
  }, [runId, refresh])

  // while paused or running, poll lightly so an approval resolved elsewhere shows up
  useEffect(() => {
    if (!run || run.finished) return
    const t = setInterval(refresh, 1500)
    return () => clearInterval(t)
  }, [run, refresh])

  return { steps, run, error, refresh }
}
