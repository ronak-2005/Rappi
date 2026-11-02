// Pick a scenario world and run the agent on it (baseline brain, or the live LLM from llm.env).
import { useEffect, useState } from 'react'
import { readApi } from '../api/read'
import { writeApi } from '../api/write'
import { Badge } from '../components/common/Badge'
import { ErrorBox } from '../components/common/ErrorBox'
import type { FixtureSummary, RunSummary } from '../types/api'

const SCENARIOS: Record<string, string> = {
  S1: 'Scenario 1 — Review a purchase recommendation',
  S4: 'Scenario 4 — Purchasing constraints',
  S2: 'Scenario 2 — Supplier cannot fulfil',
  S3: 'Scenario 3 — Demand changed',
}

export function ScenarioLauncher({ go }: { go: (hash: string) => void }) {
  const [fixtures, setFixtures] = useState<FixtureSummary[]>([])
  const [runs, setRuns] = useState<RunSummary[]>([])
  const [llm, setLlm] = useState<Record<string, any> | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [reveal, setReveal] = useState<Record<string, boolean>>({})

  useEffect(() => {
    readApi.fixtures().then(setFixtures).catch((e) => setError(e.message))
    readApi.runs().then(setRuns).catch(() => {})
    writeApi.llmHealth().then(setLlm).catch(() => setLlm({ ok: false, error: 'write_api unreachable' }))
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

  const groups = ['S1', 'S4', 'S2', 'S3'].map((s) => [s, fixtures.filter((f) => f.scenario === s)] as const)
  const liveReady = llm?.mode === 'live' && llm?.ok && llm?.tools_supported

  return (
    <>
      <ErrorBox error={error} />
      <div className="card">
        <div className="row">
          <strong>LLM</strong>
          {llm ? (
            <>
              <Badge value={llm.mode} tone="neutral" />
              <span className="mono">{llm.model || '—'}</span>
              <span className="muted small">{llm.base_url}</span>
              <span className="spacer" />
              {liveReady ? <Badge value="tools supported" tone="ok" />
                : <span className="small muted">{llm.error ?? 'live LLM not configured — edit backend/llm.env'} · baseline always works</span>}
            </>
          ) : <span className="muted">checking…</span>}
        </div>
      </div>

      {groups.map(([s, list]) => list.length > 0 && (
        <section key={s}>
          <h2 style={{ fontSize: 16 }}>{SCENARIOS[s]}</h2>
          <div className="grid two">
            {list.map((f) => (
              <div className="card scenario" key={f.id}>
                <div className="row"><Badge value={f.scenario} tone="neutral" /><span className="mono muted">{f.id}</span></div>
                <div className="title">{f.title}</div>
                <p>{f.description}</p>
                {f.trigger.recommendation && (
                  <p className="small">Recommendation: <strong>{f.trigger.recommendation.qty}</strong> × {f.trigger.recommendation.sku} at {f.trigger.recommendation.node}
                    {f.trigger.recommendation.supplier ? ` from ${f.trigger.recommendation.supplier}` : ''}</p>
                )}
                {f.trigger.supplier_event && (
                  <p className="small">Supplier on <span className="mono">{f.trigger.supplier_event.po_id}</span>: confirms
                    {' '}<strong>{f.trigger.supplier_event.confirmed_qty}</strong> — “{f.trigger.supplier_event.message}”</p>
                )}
                {f.trigger.demand_alert && (
                  <p className="small">Demand alert: “{f.trigger.demand_alert.message}”</p>
                )}
                <div className="row">
                  <button disabled={!!busy} onClick={() => start(f.id, 'baseline')}>Run · baseline</button>
                  <button className="primary" disabled={!!busy || !liveReady} onClick={() => start(f.id, 'live')}
                          title={liveReady ? '' : 'configure backend/llm.env first'}>Run · LLM</button>
                  <span className="spacer" />
                  <a className="small" onClick={() => setReveal({ ...reveal, [f.id]: !reveal[f.id] })} style={{ cursor: 'pointer' }}>
                    {reveal[f.id] ? 'hide' : 'expected answer'}
                  </a>
                </div>
                {reveal[f.id] && (
                  <pre className="json">{`decision: ${f.expected.decision.join(' | ')}${f.expected.qty_range ? `  qty ${f.expected.qty_range.join('–')}` : ''}\n\n${f.expected.notes}`}</pre>
                )}
              </div>
            ))}
          </div>
        </section>
      ))}

      {runs.length > 0 && (
        <div className="card">
          <h3>Recent runs</h3>
          <div className="table-wrap"><table>
            <thead><tr><th>Run</th><th>Scenario</th><th>Brain</th><th>Decision</th><th>Status</th></tr></thead>
            <tbody>{runs.map((r) => (
              <tr key={r.id}>
                <td><a href={`#/runs/${r.id}`} className="mono">{r.id}</a></td>
                <td className="mono">{r.fixture_id}</td>
                <td>{r.llm_mode === 'live' ? r.llm_model : r.llm_mode}</td>
                <td><Badge value={r.decision_type} /></td>
                <td><Badge value={r.status} /></td>
              </tr>
            ))}</tbody>
          </table></div>
        </div>
      )}
    </>
  )
}
