// Types mirroring the backend responses (backend/read_api/services, shared/domain).

export interface FixtureSummary {
  id: string
  scenario: 'S1' | 'S2' | 'S3' | 'S4'
  title: string
  description: string
  trigger: {
    type: 'recommendation' | 'supplier_event' | 'demand_alert'
    recommendation?: { id: string; node: string; sku: string; qty: number; supplier?: string }
    supplier_event?: { id: string; po_id: string; confirmed_qty: number; message: string }
    demand_alert?: { id: string; node: string; sku: string; message: string }
  }
  expected: { decision: string[]; qty_range?: [number, number] | null; notes: string; key_factors: string[] }
}

export interface PlanLine {
  supplier_id: string
  qty: number
  mode: 'standard' | 'express'
  delivery_day?: number | null
}

export interface TransferLine { from_node: string; qty: number }
export interface DemandAssumption { per_day: number; until_day?: number | null; reason?: string }

export interface DecisionReason { factor: string; finding: string; evidence: string[] }

export interface Decision {
  type: 'accept' | 'modify' | 'reject' | 'investigate' | 'escalate'
  node?: string
  sku?: string
  recommendation_id?: string
  lines?: PlanLine[]
  transfers?: TransferLine[]
  demand_assumption?: DemandAssumption | null
  reasons?: DecisionReason[]
  risks?: string[]
  confidence?: string
  summary?: string
  questions_for_human?: string[]
}

export interface TraceStep {
  run_id: string
  seq: number
  at: string
  state: string
  kind: string
  name: string
  payload: Record<string, any>
}

export interface POEvent { at: string; type: string; payload: Record<string, any> }

export interface PurchaseOrder {
  id: string
  node_id: string
  sku_id: string
  supplier_id: string
  qty_ordered: number
  qty_confirmed: number | null
  unit_cost: number
  mode: string
  status: string
  order_date: string
  expected_delivery: string
  created_by: string
  run_id: string | null
  notes: string
  events?: POEvent[]
}

export interface Approval {
  id: string
  run_id: string
  reasons: string[]
  plan: { decision: Decision; lines: PlanLine[]; evaluation?: Record<string, any> }
  status: 'pending' | 'approved' | 'rejected' | 'edited'
  resolved_by?: string | null
  comment: string
}

export interface RunDetail {
  id: string
  fixture_id: string
  trigger_ref: string
  status: 'running' | 'awaiting_approval' | 'completed' | 'escalated' | 'failed' | 'cancelled'
  state: string
  llm_mode: string
  llm_model: string
  decision: Decision | null
  outcome: { final_verification: string | null; verifications: any[]; executions: any[]; decisions: Decision[] } | null
  tool_calls: number
  revisions: number
  replans: number
  error: string | null
  finished: boolean
  purchase_orders: PurchaseOrder[]
  transfers: { id: string; from_node: string; to_node: string; qty: number; eta: string; status: string }[]
  approvals: Approval[]
  trigger_type: string
  context: { node: string; sku: string; recommendation_id: string }
}

export interface RunSummary {
  id: string
  fixture_id: string
  status: string
  state: string
  llm_mode: string
  llm_model: string
  started_at: string
  decision_type: string | null
}

export interface ProjectionDay {
  date: string
  day: number
  available: number
  receipts?: number
  demand: number
  lost: number
  expired: number
  close: number
  free_l: number
  over_capacity: boolean
  below_ss: boolean
}

export interface Projection {
  today: string
  safety_stock: number
  horizon_days: number
  summary: Record<string, any>
  days: ProjectionDay[]
}
