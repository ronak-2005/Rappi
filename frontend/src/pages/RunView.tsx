// One agent run, live: what it looked at, what it decided, what the rulebook said, what was ordered,
// what the supplier answered, and whether the result was verified.
import { useEffect, useMemo, useState } from 'react'
import { readApi } from '../api/read'
import { writeApi } from '../api/write'
import { ApprovalPanel } from '../components/approvals/ApprovalPanel'
import { ProjectionChart } from '../components/charts/ProjectionChart'
import { Badge } from '../components/common/Badge'
import { ErrorBox } from '../components/common/ErrorBox'
import { TraceTimeline } from '../components/trace/TraceTimeline'
import { RuleList } from '../components/validation/RuleList'
import { useRunStream } from '../hooks/useRunStream'
import type { Decision, Projection } from '../types/api'

export function RunView({ runId }: { runId: string }) {
  const { steps, run, error, refresh } = useRunStream(runId)
  const [actual, setActual] = useState<Projection | null>(null)

  const decision: Decision | null = useMemo(() => {
    const ds = steps.filter((s) => s.kind === 'decision')
    return (ds.length ? (ds[ds.length - 1].payload as Decision) : null) ?? run?.decision ?? null
  }, [steps, run])
  const validation = [...steps].reverse().find((s) => s.kind === 'validation')
  const planned = [...steps].reverse().find((s) => s.kind === 'tool_call' && s.name === 'project_inventory' && s.payload.ok)
  const verifications = steps.filter((s) => s.kind === 'verification')
  const pending = run?.approvals.find((a) => a.status === 'pending')

  useEffect(() => {  // after the supplier answered: projection of the world as it is now
    if (run?.finished && run.purchase_orders.length && run.context?.node) {
      readApi.projection(run.context.node, run.context.sku, [], run.context.recommendation_id).then(setActual).catch(() => {})
    }
  }, [run?.finished, run?.purchase_orders.length])

  if (!run) return <><ErrorBox error={error} /><p className="muted">Loading run…</p></>

  return (
    <>
      <ErrorBox error={error || run.error} />
      <div className="card">
        <div className="row">
          <span className="mono">{run.id}</span>
          <Badge value={run.status} />
          <span className="mono muted small">{run.state}</span>
          <span className="spacer" />
          <span className="small muted">scenario <span className="mono">{run.fixture_id}</span> · brain <strong>{run.llm_mode === 'live' ? run.llm_model : run.llm_mode}</strong>
            · {run.tool_calls} tool calls · {run.revisions} revisions · {run.replans} re-plans</span>
          {!run.finished && run.status !== 'awaiting_approval' && <button onClick={() => writeApi.cancel(run.id).then(refresh)}>Cancel</button>}
        </div>
      </div>

      <div className="grid run">
        <div className="card">
          <h3>Trace <span className="muted small">(click a step for details)</span></h3>
          <TraceTimeline steps={steps} />
        </div>

        <div>
          {pending && <ApprovalPanel approval={pending} onDone={refresh} />}

          {decision && (
            <div className="card">
              <h3>Decision</h3>
              <div className="row"><span className="decision-type">{decision.type}</span>
                {decision.confidence && <Badge value={`confidence ${decision.confidence}`} tone="neutral" />}</div>
              {decision.summary && <p>{decision.summary}</p>}
              {!!decision.lines?.length && (
                <table><thead><tr><th>Supplier</th><th>Qty</th><th>Mode</th><th>Delivery</th></tr></thead>
                  <tbody>{decision.lines.map((l, i) => (
                    <tr key={i}><td>{l.supplier_id}</td><td><strong>{l.qty}</strong></td><td>{l.mode}</td>
                      <td>{l.delivery_day != null ? `day +${l.delivery_day}` : 'earliest'}</td></tr>))}</tbody></table>
              )}
              {!!decision.reasons?.length && <><h4>Why</h4>{decision.reasons.map((r, i) => (
                <div className="reason" key={i}><strong>{r.factor}</strong>: {r.finding}
                  {!!r.evidence?.length && <span className="mono muted"> [{r.evidence.join(', ')}]</span>}</div>))}</>}
              {!!decision.risks?.length && <><h4>Risks</h4><ul className="small">{decision.risks.map((r) => <li key={r}>{r}</li>)}</ul></>}
              {!!decision.questions_for_human?.length && <><h4>Questions for the buyer</h4>
                <ul className="small">{decision.questions_for_human.map((q) => <li key={q}>{q}</li>)}</ul></>}
            </div>
          )}

          {validation && (
            <div className="card">
              <h3>Rulebook</h3>
              <RuleList results={validation.payload.results ?? []} />
            </div>
          )}

          {planned && (
            <div className="card">
              <h3>Projection of the chosen plan <span className="muted small">(what the agent saw)</span></h3>
              <ProjectionChart projection={planned.payload.result as Projection} />
            </div>
          )}

          {!!run.purchase_orders.length && (
            <div className="card">
              <h3>Purchase orders &amp; supplier answers</h3>
              <div className="table-wrap"><table>
                <thead><tr><th>PO</th><th>Supplier</th><th>Ordered</th><th>Confirmed</th><th>Delivery</th><th>Status</th><th>Supplier said</th></tr></thead>
                <tbody>{run.purchase_orders.map((p) => (
                  <tr key={p.id}><td className="mono">{p.id}</td><td>{p.supplier_id}</td><td>{p.qty_ordered}</td>
                    <td>{p.qty_confirmed ?? '—'}</td><td>{p.expected_delivery}</td><td><Badge value={p.status} /></td>
                    <td className="small muted">{p.notes}</td></tr>))}</tbody>
              </table></div>
            </div>
          )}

          {verifications.map((v) => (
            <div className="card" key={v.seq}>
              <h3>Verification <Badge value={v.name} /></h3>
              <p className="small">{v.payload.message}</p>
              {!!v.payload.differences?.length && <ul className="small">{v.payload.differences.map((d: string) => <li key={d}>{d}</li>)}</ul>}
              <p className="small muted">expected lost {v.payload.expected?.lost_units} · actual lost {v.payload.actual?.lost_units}
                · actual min stock {v.payload.actual?.min_close} · remaining need {v.payload.residual_need}</p>
            </div>
          ))}

          {actual && (
            <div className="card">
              <h3>Projection now <span className="muted small">(with the suppliers' real answers)</span></h3>
              <ProjectionChart projection={actual} />
            </div>
          )}
        </div>
      </div>
    </>
  )
}
