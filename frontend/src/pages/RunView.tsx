// One agent run. The verdict leads; everything below explains it: the stock picture, the reasons,
// the rule check, the orders and what the suppliers answered, and the full sequence of what the agent did.
import { useEffect, useMemo, useState } from 'react'
import { readApi } from '../api/read'
import { writeApi } from '../api/write'
import { ApprovalPanel } from '../components/approvals/ApprovalPanel'
import { ProjectionChart } from '../components/charts/ProjectionChart'
import { Badge } from '../components/common/Badge'
import { ErrorBox } from '../components/common/ErrorBox'
import { TOOL_WORDS, TraceTimeline } from '../components/trace/TraceTimeline'
import { RuleList } from '../components/validation/RuleList'
import { useRunStream } from '../hooks/useRunStream'
import type { Decision, Projection, RunDetail, TraceStep } from '../types/api'

const day = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

function verdict(run: RunDetail, d: Decision | null, names: Record<string, string>): string {
  if (!d) return run.status === 'failed' ? 'The run failed before a decision' : 'Working on it…'
  const name = (id: string) => names[id] ?? id
  const arrival = (supplier: string, qty: number) => {
    const po = run.purchase_orders.find((p) => p.supplier_id === supplier && p.qty_ordered === qty)
    return po ? `, arriving ${day(po.expected_delivery)}` : ''
  }
  const parts = [
    ...(d.lines ?? []).map((l) => `buy ${l.qty} from ${name(l.supplier_id)}${l.mode === 'express' ? ' by express' : ''}${arrival(l.supplier_id, l.qty)}`),
    ...(d.transfers ?? []).map((t) => `move ${t.qty} from the ${t.from_node} store`),
  ]
  if (run.status === 'awaiting_approval' && parts.length) return `Proposed, needs your approval: ${parts.join(' and ')}`
  const short = run.purchase_orders.find((p) => p.qty_confirmed != null && p.qty_confirmed < p.qty_ordered)
  if (run.replans > 0 && short && d.type === 'modify') {
    return `${name(short.supplier_id)} sent ${short.qty_confirmed} of ${short.qty_ordered}, so the agent re-planned: ${parts.join(' and ')}`
  }
  switch (d.type) {
    case 'accept': return parts.length ? `Accept: ${parts.join(' and ')}` : 'Keep the current plan: nothing more to buy'
    case 'modify': return `Change the plan: ${parts.join(' and ')}`
    case 'reject': return 'Don’t buy: stock and open orders already cover the need'
    case 'investigate': return 'Check the stock count first: nothing was bought'
    case 'escalate': return 'Handed to a buyer: no safe plan was found'
  }
}

function triggerText(steps: TraceStep[]): string {
  const sit = steps.find((s) => s.kind === 'info' && s.name === 'situation')?.payload
  if (!sit) return ''
  if (sit.recommendation) return `Recommendation: buy ${sit.recommendation.qty} × ${sit.recommendation.sku} from ${sit.recommendation.supplier}`
  if (sit.event) return `Supplier message on ${sit.purchase_order?.id}: “${sit.event.message}”`
  if (sit.alert) return `Demand alert: “${sit.alert.message}”`
  return ''
}

export function RunView({ runId }: { runId: string }) {
  const { steps, run, error, refresh } = useRunStream(runId)
  const [actual, setActual] = useState<Projection | null>(null)
  const [showPlanned, setShowPlanned] = useState(false)
  const [names, setNames] = useState<Record<string, string>>({})
  const [title, setTitle] = useState('')

  const decision: Decision | null = useMemo(() => {
    const ds = steps.filter((s) => s.kind === 'decision')
    return run?.decision ?? (ds.length ? (ds[ds.length - 1].payload as Decision) : null)
  }, [steps, run])
  const validation = [...steps].reverse().find((s) => s.kind === 'validation')
  const planned = [...steps].reverse().find((s) => s.kind === 'tool_call' && s.name === 'project_inventory' && s.payload.ok)
  const verifications = steps.filter((s) => s.kind === 'verification')
  const evidenceName = Object.fromEntries(steps.filter((s) => s.kind === 'tool_call')
    .map((s) => [s.payload.id, TOOL_WORDS[s.name] ?? s.name]))
  const pending = run?.approvals.find((a) => a.status === 'pending')

  useEffect(() => {
    if (!run?.context?.sku) return
    readApi.suppliers(run.context.sku).then((r) =>
      setNames(Object.fromEntries(r.suppliers.map((s) => [s.supplier_id, s.supplier_name])))).catch(() => {})
    readApi.fixtures().then((fx) => setTitle(fx.find((f) => f.id === run.fixture_id)?.title ?? '')).catch(() => {})
  }, [run?.context?.sku, run?.fixture_id])

  useEffect(() => {  // after the suppliers answered: the stock picture as it really is now
    if (run?.finished && (run.purchase_orders.length || run.transfers?.length) && run.context?.node) {
      readApi.projection(run.context.node, run.context.sku, [], run.context.recommendation_id).then(setActual).catch(() => {})
    }
  }, [run?.finished, run?.purchase_orders.length, run?.transfers?.length])

  if (!run) return <><ErrorBox error={error} /><p className="muted">Loading run…</p></>

  const chart = actual && !showPlanned
    ? { p: actual, t: 'Stock by day, with the suppliers’ real answers', n: 'Includes every order and transfer as confirmed.' }
    : planned ? { p: planned.payload.result as Projection, t: 'Stock by day, if the plan goes as intended', n: 'The agent’s own projection before acting.' } : null
  const finalV = run.outcome?.final_verification

  return (
    <>
      <a className="back" href="#/">← All scenarios</a>
      <ErrorBox error={error || run.error} />

      <section className="verdict">
        <div className="kind">
          <Badge value={run.status} />
          <span>{title || run.fixture_id}</span>
        </div>
        <h1>{verdict(run, decision, names)}</h1>
        {decision?.summary && <p className="sub">{decision.summary.replace(/^(accept|modify|reject|investigate|escalate)\s*:\s*/i, '')}</p>}
        <div className="facts">
          <span><strong>{triggerText(steps) ? 'Trigger' : 'Run'}</strong>{triggerText(steps) || run.id}</span>
          <span><strong>Decided by</strong>{run.llm_mode === 'live' ? run.llm_model : 'Rules only (no LLM)'}</span>
          <span><strong>Tool calls</strong>{run.tool_calls}</span>
          {run.replans > 0 && <span><strong>Re-plans</strong>{run.replans}</span>}
          {finalV && <span><strong>Result</strong><Badge value={finalV} /></span>}
          {!run.finished && run.status !== 'awaiting_approval' &&
            <span><button onClick={() => writeApi.cancel(run.id).then(refresh)}>Stop this run</button></span>}
        </div>
      </section>

      {pending && <ApprovalPanel approval={pending} names={names} onDone={refresh} />}

      {chart && (
        <section className="section">
          <ProjectionChart projection={chart.p} title={chart.t} note={chart.n} />
          {actual && planned && (
            <button className="link small" onClick={() => setShowPlanned(!showPlanned)}>
              {showPlanned ? 'Show what really happened' : 'Compare with what the agent planned'}
            </button>
          )}
        </section>
      )}

      <div className="cols">
        <div>
          {!!decision?.reasons?.length && (
            <section className="section">
              <h2>Why</h2>
              {decision.demand_assumption && (
                <p className="small" style={{ marginBottom: 8 }}>
                  <Badge value="pending" tone="warn" /> Planned on <strong>{decision.demand_assumption.per_day} a day</strong>
                  {decision.demand_assumption.until_day != null ? ` until day +${decision.demand_assumption.until_day}, then the forecast` : ' instead of the forecast'}.
                </p>
              )}
              <ul className="reasons">
                {decision.reasons.map((r, i) => (
                  <li key={i}>
                    <span className="factor">{r.factor.replaceAll('_', ' ')}</span>. {r.finding}
                    {!!r.evidence?.length && <span className="evidence" title="Tool results this reason is based on">
                      {[...new Set(r.evidence.map((e) => evidenceName[e] ?? 'a tool result'))].map((n) => <span key={n}>{n}</span>)}</span>}
                  </li>
                ))}
              </ul>
              {!!decision.questions_for_human?.length && (
                <><h3 style={{ marginTop: 12 }}>Questions for the buyer</h3>
                  <ul className="small">{decision.questions_for_human.map((q) => <li key={q}>{q}</li>)}</ul></>
              )}
            </section>
          )}
          <section className="section">
            <h2>What the agent did</h2>
            <TraceTimeline steps={steps} />
          </section>
        </div>

        <div>
          {validation && (
            <section className="section">
              <h2>Rule check</h2>
              <RuleList results={validation.payload.results ?? []} />
            </section>
          )}
          {(run.purchase_orders.length > 0 || run.transfers?.length > 0) && (
            <section className="section">
              <h2>Orders and what suppliers said</h2>
              <ul className="reasons">
                {run.purchase_orders.map((p) => (
                  <li key={p.id}>
                    <div className="row"><strong>{names[p.supplier_id] ?? p.supplier_id}</strong><Badge value={p.status} /></div>
                    <div className="small">Ordered {p.qty_ordered}, confirmed {p.qty_confirmed ?? '—'}, arriving {day(p.expected_delivery)}</div>
                    {p.notes && <div className="small muted">“{p.notes}”</div>}
                    <div className="small muted">{p.id}</div>
                  </li>
                ))}
                {run.transfers?.map((t) => (
                  <li key={t.id}>
                    <div className="row"><strong>Transfer from {t.from_node}</strong><Badge value={t.status} /></div>
                    <div className="small">{t.qty} units, arriving {day(t.eta)}</div>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {verifications.length > 0 && (
            <section className="section">
              <h2>Result check</h2>
              <ul className="reasons">
                {verifications.map((v) => (
                  <li key={v.seq}>
                    <Badge value={v.name} />
                    <p className="small" style={{ marginTop: 4 }}>{v.payload.message}</p>
                    {!!v.payload.differences?.length && <ul className="small muted">{v.payload.differences.map((x: string) => <li key={x}>{x}</li>)}</ul>}
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </>
  )
}
