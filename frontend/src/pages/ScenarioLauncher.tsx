// Pick a situation and let the agent handle it, with the LLM from llm.env or with rules only (no LLM).
import { useEffect, useState } from 'react'
import { readApi } from '../api/read'
import { writeApi } from '../api/write'
import { Badge } from '../components/common/Badge'
import { ErrorBox } from '../components/common/ErrorBox'
import type { FixtureSummary, RunSummary } from '../types/api'

const GROUPS: { id: string; title: string; text: string }[] = [
  { id: 'S1', title: 'Review a recommendation', text: 'The replenishment system proposes an order. Is it right?' },
  { id: 'S2', title: 'A supplier can’t deliver in full', text: 'A supplier confirms only part of an order. Does it matter, and what covers the gap?' },
  { id: 'S3', title: 'Demand changed', text: 'Sales moved away from the forecast. Is it a real change, a promotion, or noise?' },
  { id: 'S4', title: 'Constraints and failures', text: 'Storage, budget, shelf life, slow delivery, and suppliers that answer differently than expected.' },
]

function trigger(f: FixtureSummary): string {
  const t = f.trigger
  if (t.recommendation) return `Recommended: ${t.recommendation.qty} × ${t.recommendation.sku} from ${t.recommendation.supplier} for ${t.recommendation.node}.`
  if (t.supplier_event) return `Supplier on ${t.supplier_event.po_id}: “${t.supplier_event.message}”`
  if (t.demand_alert) return `Alert: “${t.demand_alert.message}”`
  return ''
}

export function ScenarioLauncher({ go }: { go: (hash: string) => void }) {
  const [fixtures, setFixtures] = useState<FixtureSummary[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [llm, setLlm] = useState<Record<string, any> | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [open, setOpen] = useState<string | null>(null)

  useEffect(() => {
    readApi.fixtures().then(setFixtures).catch((e) => setError(e.message))
    readApi.runs().then(setRuns).catch(() => {})
    writeApi.llmHealth().then(setLlm).catch(() => setLlm({ ok: false, error: 'The write service isn’t running. Start everything with make dev.' }))
  }, [])

  async function start(id: string, mode: 'live' | 'baseline') {
    setBusy(id + mode)
    setError(null)
    try {
      const r = await writeApi.startRun(id, mode)
      go(`#/runs/${r.run_id}`)
    } catch (e) {
      setError((e as Error).message)
      setBusy(null)
    }
  }

  const liveReady = llm?.mode === 'live' && llm?.ok && llm?.tools_supported

  return (
    <>
      <div className="intro">
        <h1>Purchasing situations</h1>
        <p className="muted">Each one loads a store’s stock, orders, suppliers and budget, then lets the agent investigate,
          decide, place orders and check what the suppliers really did.</p>
      </div>
      <ErrorBox error={error} />
      <div className="brain">
        <strong>LLM</strong>
        {!llm ? <span className="muted">Checking…</span> : liveReady
          ? <><span>{llm.model}</span><span className="status ok">Ready, supports tools</span></>
          : <span className="muted">{llm.error ?? 'Not configured.'} Set LLM_BASE_URL, LLM_API_KEY and LLM_MODEL in backend/llm.env.
            “Run with rules only” always works.</span>}
      </div>

      {GROUPS.map((g) => {
        const list = fixtures.filter((f) => f.scenario === g.id)
        if (!list.length) return null
        return (
          <section className="group" key={g.id}>
            <h2>{g.title}</h2>
            <p>{g.text}</p>
            <ul className="scenario-list">
              {list.map((f) => (
                <li className="scenario" key={f.id}>
                  <span className="title">{f.title}</span>
                  <span className="actions">
                    <button className="primary" disabled={!!busy || !liveReady} onClick={() => start(f.id, 'live')}
                            title={liveReady ? 'Run with the LLM' : 'Configure backend/llm.env first'}>
                      {busy === f.id + 'live' ? 'Starting…' : 'Run with LLM'}</button>
                    <button disabled={!!busy} onClick={() => start(f.id, 'baseline')}>
                      {busy === f.id + 'baseline' ? 'Starting…' : 'Run with rules only'}</button>
                  </span>
                  <span className="trigger">
                    {trigger(f)}{' '}
                    <button className="link small" onClick={() => setOpen(open === f.id ? null : f.id)} aria-expanded={open === f.id}>
                      {open === f.id ? 'Hide the expected answer' : 'Expected answer'}</button>
                  </span>
                  {open === f.id && (
                    <div className="expected">{`Expected: ${f.expected.decision.join(' or ')}${f.expected.qty_range && f.expected.qty_range[1] > 0 ? `, ${f.expected.qty_range[0] === f.expected.qty_range[1] ? f.expected.qty_range[0] : f.expected.qty_range.join('–')} units` : ''}\n\n${f.expected.notes}`}</div>
                  )}
                </li>
              ))}
            </ul>
          </section>
        )
      })}

      {runs.length > 0 && (
        <section className="group">
          <h2>Recent runs</h2>
          <div className="table-wrap"><table>
            <thead><tr><th>Situation</th><th>Decided by</th><th>Decision</th><th>Status</th><th>Started</th></tr></thead>
            <tbody>{runs.map((r) => (
              <tr key={r.id}>
                <td><a href={`#/runs/${r.id}`}>{fixtures.find((f) => f.id === r.fixture_id)?.title ?? r.fixture_id}</a></td>
                <td>{r.llm_mode === 'live' ? r.llm_model : 'Rules only'}</td>
                <td>{r.decision_type ? r.decision_type.charAt(0).toUpperCase() + r.decision_type.slice(1) : '—'}</td>
                <td><Badge value={r.status} /></td>
                <td className="muted">{new Date(r.started_at).toLocaleString('en-GB', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}</td>
              </tr>
            ))}</tbody>
          </table></div>
        </section>
      )}
    </>
  )
}
