// The agent's run, step by step: LLM turns, tool calls, gates, rulebook, approvals, actions, verification.
import { useState } from 'react'
import type { TraceStep } from '../../types/api'
import { Badge } from '../common/Badge'
import { Json } from '../common/Json'

function headline(s: TraceStep): string {
  const p = s.payload
  switch (s.kind) {
    case 'llm_message':
      return p.tool_calls?.length ? `asks: ${p.tool_calls.map((t: any) => t.name).join(', ')}` : `says: ${(p.text || '').slice(0, 120)}`
    case 'tool_call':
      return `${s.name}${p.ok ? '' : ' ✗ error'}`
    case 'decision':
      return `decision: ${s.name} — ${(p.summary || '').slice(0, 100)}`
    case 'gate':
      return p.passed ? 'evidence gate passed' : `evidence gate: ${p.error || 'rejected'}`
    case 'validation':
      return p.passed ? (p.requires_approval ? 'rulebook: valid, needs human approval' : 'rulebook: passed') : 'rulebook: REJECTED (hard rule)'
    case 'approval':
      return `approval ${s.name}${p.by ? ` by ${p.by}` : ''}`
    case 'action':
      return `placed ${p.lines?.length ?? 0} PO(s): ${(p.lines || []).map((l: any) => `${l.po_id} ${l.qty_confirmed}/${l.qty_requested} ${l.status}`).join('; ')}`
    case 'verification':
      return `verification: ${s.name} — ${p.message || ''}`
    default:
      return s.name
  }
}

export function TraceTimeline({ steps }: { steps: TraceStep[] }) {
  const [open, setOpen] = useState<number | null>(null)
  // an LLM turn that only requests tools is shown by the tool steps themselves; keep turns with text
  const visible = steps.filter((s) => s.kind !== 'llm_message' || (s.payload.text || '').trim())
  if (!steps.length) return <p className="muted">Waiting for the first step…</p>
  return (
    <ul className="timeline">
      {visible.map((s) => (
        <li key={s.seq} className={`k-${s.kind}`}>
          <div className="head" onClick={() => setOpen(open === s.seq ? null : s.seq)}>
            <span className="state">#{s.seq} {s.state}</span>
            {s.kind === 'verification' && <Badge value={s.name} />}
            {s.kind === 'validation' && <Badge value={s.payload.passed ? (s.payload.requires_approval ? 'pending' : 'passed') : 'rejected'} />}
            <span>{headline(s)}</span>
          </div>
          {open === s.seq && <Json value={s.payload} />}
        </li>
      ))}
    </ul>
  )
}
