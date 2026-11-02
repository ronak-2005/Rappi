// Read API (:8001) — queries only. Mirrors backend/read_api/controllers.
import { READ_API, request } from './client'
import type { Approval, FixtureSummary, PlanLine, Projection, PurchaseOrder, RunDetail, RunSummary, TraceStep } from '../types/api'

const get = <T,>(path: string) => request<T>(READ_API, path)

export const readApi = {
  world: () => get<{ fixture_id: string; today: string; weekday: string }>('/world'),
  fixtures: () => get<FixtureSummary[]>('/fixtures'),
  runs: () => get<RunSummary[]>('/runs'),
  run: (id: string) => get<RunDetail>(`/runs/${id}`),
  trace: (id: string) => get<TraceStep[]>(`/runs/${id}/trace`),
  approvals: (status?: string) => get<Approval[]>(`/approvals${status ? `?status=${status}` : ''}`),
  purchaseOrders: () => get<PurchaseOrder[]>('/purchase-orders'),
  projection: (node: string, sku: string, lines: PlanLine[] = [], recommendationId?: string) =>
    request<Projection>(READ_API, `/nodes/${node}/skus/${sku}/projection`, {
      method: 'POST',
      body: JSON.stringify({ plan: { lines }, recommendation_id: recommendationId ?? null }),
    }),
  evals: () => get<Record<string, any>>('/evals/latest'),
}
