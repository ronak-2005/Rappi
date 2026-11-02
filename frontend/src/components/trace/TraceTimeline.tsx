// What the agent did, as the sequence of phases it actually went through:
// investigate → decide → check the rules → (human approval) → place orders → verify → (re-plan) …
// Each phase has a one-line summary; its individual steps open on demand.
import { useState } from 'react'
import type { TraceStep } from '../../types/api'
import { Badge } from '../common/Badge'
import { Json } from '../common/Json'
import { capitalize, humanize, TOOL_WORDS } from '../../format'

type Key = 'investigate' | 'replan' | 'decide' | 'check' | 'approval' | 'act' | 'verify' | 'outcome'
const TITLES: Record<Key, string> = {
  investigate: 'Investigated', replan: 'Re-planned', decide: 'Decided', check: 'Checked the rules',
  approval: 'Asked a buyer', act: 'Placed orders', verify: 'Checked the result', outcome: 'Finished',
}

interface Phase { key: Key; steps: TraceStep[] }

function phaseOf(s: TraceStep, replanning: boolean): Key | null {
  switch (s.kind) {
    case 'tool_call': return replanning ? 'replan' : 'investigate'
    case 'llm_message': return s.payload.text?.trim() ? (replanning ? 'replan' : 'investigate') : null
    case 'decision': case 'gate': return 'decide'
    case 'validation': return 'check'
    case 'approval': return 'approval'
    case 'action': return 'act'
    case 'verification': return 'verify'
    case 'info': return s.name === 'supplier_learning' ? 'act' : s.name === 'situation' ? null : 'outcome'
    case 'error': return 'outcome'
    default: return null
  }
}

function group(steps: TraceStep[]): Phase[] {
  const out: Phase[] = []
  let replanning = false
  for (const s of steps) {
    const key = phaseOf(s, replanning)
    if (s.kind === 'verification' && s.name === 'UNACCEPTABLE') replanning = true
    if (s.kind === 'approval' && s.name === 'rejected') replanning = true
    if (s.kind === 'decision') replanning = false
    if (!key) continue
    const last = out[out.length - 1]
    if (last && last.key === key) last.steps.push(s)
    else out.push({ key, steps: [s] })
  }
  return out
}

function summary(p: Phase): { text: string; status?: string } {
  const s = p.steps
  switch (p.key) {
    case 'investigate': case 'replan': {
      const tools = s.filter((x) => x.kind === 'tool_call')
      const words = [...new Set(tools.map((t) => TOOL_WORDS[t.name] ?? t.name))]
      const failed = tools.filter((t) => !t.payload.ok).length
      return { text: `Looked at ${words.join(', ')}.${failed ? ` ${failed} call(s) failed and were retried.` : ''}` }
    }
    case 'decide': {
      const d = [...s].reverse().find((x) => x.kind === 'decision')
      const gates = s.filter((x) => x.kind === 'gate' && !x.payload.passed)
      const back = gates.length ? ` The evidence check sent it back ${gates.length} time(s) first.` : ''
      const said = (d?.payload.summary ?? '').replace(/^(accept|modify|reject|investigate|escalate)\s*:?\s*/i, '')
      return { text: `${said ? capitalize(said) : 'Submitted a decision.'}${back}`, status: d?.name }
    }
    case 'check': {
      const v = s[s.length - 1].payload
      const failed = (v.results ?? []).filter((r: { passed: boolean }) => !r.passed)
      if (!v.passed) return { text: `Blocked by ${names(failed.filter((r: { kind: string }) => r.kind === 'hard'))}.`, status: 'rejected' }
      if (v.requires_approval) return { text: `Allowed, but needs a buyer’s approval for ${names(failed)}.`, status: 'pending' }
      return { text: `All ${(v.results ?? []).length} rules passed.`, status: 'passed' }
    }
    case 'approval': {
      const last = s[s.length - 1]
      return { text: last.name === 'requested' ? `Waiting: ${(last.payload.reasons ?? []).join('; ')}` : `${capitalize(last.name)} by ${last.payload.by ?? 'a buyer'}.`, status: last.name === 'requested' ? 'pending' : last.name }
    }
    case 'act': {
      const a = s.find((x) => x.kind === 'action')?.payload
      const lines = (a?.lines ?? []).map((l: { supplier_id: string; po_id: string; qty_confirmed: number; qty_requested: number }) =>
        l.supplier_id.startsWith('transfer:') ? `moved ${l.qty_confirmed} from ${l.supplier_id.slice(9)}`
          : `${l.po_id}: ${l.supplier_id} confirmed ${l.qty_confirmed} of ${l.qty_requested}`)
      return { text: lines.join('; ') || 'Placed orders.' }
    }
    case 'verify': {
      const v = s[s.length - 1]
      return { text: v.payload.message ?? '', status: v.name }
    }
    case 'outcome': {
      const e = s.find((x) => x.name === 'escalated' || x.kind === 'error')
      const f = s.find((x) => x.name === 'finished')
      return { text: e ? (e.payload.reason ?? e.payload.error) : '', status: f?.payload.status ?? (e ? 'failed' : undefined) }
    }
  }
}

const names = (rs: { rule: string }[]) => rs.map((r) => humanize(r.rule)).join(', ') || '—'

function stepLabel(s: TraceStep): string {
  if (s.kind === 'tool_call') return `${TOOL_WORDS[s.name] ? capitalize(TOOL_WORDS[s.name]) : s.name}${s.payload.ok ? '' : ' (error)'}`
  if (s.kind === 'llm_message') return `Model note: ${(s.payload.text || '').slice(0, 140)}`
  if (s.kind === 'gate') return s.payload.passed ? 'Evidence check passed' : `Evidence check: ${s.payload.error}`
  return `${capitalize(s.kind)}: ${humanize(s.name)}`
}

export function TraceTimeline({ steps }: { steps: TraceStep[] }) {
  const [openPhase, setOpenPhase] = useState<number | null>(null)
  const [openStep, setOpenStep] = useState<number | null>(null)
  const phases = group(steps)
  if (!phases.length) return <p className="muted">Starting…</p>
  return (
    <ol className="phases">
      {phases.map((p, i) => {
        const sm = summary(p)
        return (
          <li className="phase" key={i}>
            <h3>{TITLES[p.key]} {sm.status && <Badge value={sm.status} />}</h3>
            <p className="summary">{sm.text}</p>
            <button className="link small" onClick={() => setOpenPhase(openPhase === i ? null : i)} aria-expanded={openPhase === i}>
              {openPhase === i ? 'Hide steps' : `Show ${p.steps.length} step${p.steps.length > 1 ? 's' : ''}`}
            </button>
            {openPhase === i && (
              <ul className="steps">
                {p.steps.map((s) => (
                  <li key={s.seq}>
                    <button className="link" onClick={() => setOpenStep(openStep === s.seq ? null : s.seq)}>{stepLabel(s)}</button>
                    {openStep === s.seq && <Json value={s.payload} />}
                  </li>
                ))}
              </ul>
            )}
          </li>
        )
      })}
    </ol>
  )
}
