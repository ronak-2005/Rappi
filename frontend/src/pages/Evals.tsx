// The latest evaluation report (written by `make eval`): pass rates per check, per brain.
import { useEffect, useState } from 'react'
import { readApi } from '../api/read'
import { ErrorBox } from '../components/common/ErrorBox'

const pct = (x: number) => `${Math.round(x * 100)}%`

export function Evals() {
  const [report, setReport] = useState<Record<string, any> | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { readApi.evals().then(setReport).catch((e) => setError(e.message)) }, [])
  if (error) return <ErrorBox error={error} />
  if (!report) return <p className="muted">Loading…</p>
  if (!report.available) return <div className="card">{report.message}</div>
  const brains: string[] = report.brains ?? []
  return (
    <>
      <div className="card">
        <h3>Evaluation report</h3>
        <p className="small muted">Generated {report.generated_at} · {report.repeats} repeat(s) per scenario · brains: {brains.join(', ')}</p>
        <div className="table-wrap"><table>
          <thead><tr><th>Scenario</th>{brains.map((b) => <th key={b}>{b}</th>)}</tr></thead>
          <tbody>{(report.fixtures ?? []).map((f: any) => (
            <tr key={f.id}><td className="mono">{f.id}</td>{brains.map((b) => {
              const c = f.by_brain?.[b]
              return <td key={b}>{c ? `${pct(c.all_checks_pass_rate)} all-pass · ${c.decisions.join(', ')}` : '—'}</td>
            })}</tr>))}</tbody>
        </table></div>
      </div>
      <div className="card">
        <h3>Pass rate per check</h3>
        <div className="table-wrap"><table>
          <thead><tr><th>Check</th><th>Group</th>{brains.map((b) => <th key={b}>{b}</th>)}</tr></thead>
          <tbody>{(report.checks ?? []).map((c: any) => (
            <tr key={c.name}><td>{c.name}</td><td className="muted">{c.group}</td>
              {brains.map((b) => <td key={b}>{c.by_brain?.[b] != null ? pct(c.by_brain[b]) : '—'}</td>)}</tr>))}</tbody>
        </table></div>
      </div>
    </>
  )
}
