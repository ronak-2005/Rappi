// The latest evaluation report (written by `make eval`): which situations each brain gets fully right.
import { useEffect, useState } from 'react'
import { readApi } from '../api/read'
import { ErrorBox } from '../components/common/ErrorBox'
import { humanize } from '../format'

const pct = (x: number | null | undefined) => (x == null ? '—' : `${Math.round(x * 100)}%`)

export function Evals() {
  const [report, setReport] = useState<Record<string, any> | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { readApi.evals().then(setReport).catch((e) => setError(e.message)) }, [])
  if (error) return <ErrorBox error={error} />
  if (!report) return <p className="muted">Loading…</p>
  const brains: string[] = report.brains ?? []
  return (
    <>
      <div className="intro">
        <h1>Evaluation</h1>
        <p className="muted">A run counts as passed only if every check passes: the decision, the evidence it gathered, the rules,
          the orders it placed, and how it verified and recovered.</p>
      </div>
      {!report.available ? <p>No report yet. Run <code>make eval</code> to create one.</p> : (
        <>
          <p className="small muted" style={{ marginBottom: 12 }}>Generated {new Date(report.generated_at).toLocaleString('en-GB')}.</p>
          <div className="table-wrap"><table>
            <thead><tr><th>Situation</th><th>Expected</th>{brains.map((b) => <th key={b}>{b === 'baseline' ? 'Rules only' : b}</th>)}</tr></thead>
            <tbody>{(report.fixtures ?? []).map((f: any) => (
              <tr key={f.id}><td>{f.title ?? f.id}</td><td className="muted">{(f.expected ?? []).join(' or ')}</td>{brains.map((b) => {
                const c = f.by_brain?.[b]
                return <td key={b}>{c ? <><span className={`status ${c.all_checks_pass_rate === 1 ? 'ok' : 'bad'}`}>
                  {c.all_checks_pass_rate === 1 ? 'Passed' : 'Failed'}</span>
                  {c.failed_checks?.length ? <div className="small muted">{humanize(c.failed_checks.join(', '))}</div> : null}</> : '—'}</td>
              })}</tr>))}</tbody>
          </table></div>
          <section className="section" style={{ marginTop: 24 }}>
            <h2>Pass rate per check</h2>
            <div className="table-wrap"><table>
              <thead><tr><th>Check</th><th>Area</th>{brains.map((b) => <th key={b} className="num">{b === 'baseline' ? 'Rules only' : b}</th>)}</tr></thead>
              <tbody>{(report.checks ?? []).map((c: any) => (
                <tr key={c.name}><td>{humanize(c.name)}</td><td className="muted">{c.group}</td>
                  {brains.map((b) => <td key={b} className="num">{pct(c.by_brain?.[b])}</td>)}</tr>))}</tbody>
            </table></div>
          </section>
        </>
      )}
    </>
  )
}
