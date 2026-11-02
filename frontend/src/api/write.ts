// Write API (:8002) — commands. Mirrors backend/write_api/controllers.
import { WRITE_API, request } from './client'

const post = <T,>(path: string, body: unknown = {}) =>
  request<T>(WRITE_API, path, { method: 'POST', body: JSON.stringify(body) })

export const writeApi = {
  startRun: (fixtureId: string, llmMode: 'live' | 'baseline') =>
    post<{ run_id: string; llm_mode: string; llm_model: string }>('/runs', { fixture_id: fixtureId, llm_mode: llmMode }),
  cancel: (runId: string) => post(`/runs/${runId}/cancel`),
  resolveApproval: (id: string, decision: 'approve' | 'reject' | 'edit', comment: string, lines?: unknown[]) =>
    post(`/approvals/${id}`, { decision, comment, lines, by: 'buyer (UI)' }),
  llmHealth: () => request<Record<string, any>>(WRITE_API, '/health/llm'),
}
