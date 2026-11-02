// A human approves, rejects or edits a plan that broke a soft rule. Edits are re-checked against hard rules.
import { useState } from 'react'
import { writeApi } from '../../api/write'
import type { Approval } from '../../types/api'
import { ErrorBox } from '../common/ErrorBox'

export function ApprovalPanel({ approval, onDone }: { approval: Approval; onDone: () => void }) {
  const [comment, setComment] = useState('')
  const [qty, setQty] = useState<number[]>(approval.plan.lines.map((l) => l.qty))
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const edited = qty.some((q, i) => q !== approval.plan.lines[i].qty)

  async function act(decision: 'approve' | 'reject' | 'edit') {
    setBusy(true)
    setError(null)
    try {
      const lines = decision === 'edit' ? approval.plan.lines.map((l, i) => ({ ...l, qty: qty[i] })) : undefined
      await writeApi.resolveApproval(approval.id, decision, comment, lines)
      onDone()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="card approval">
      <h3>⚠️ Human approval needed</h3>
      <p className="small muted">The plan passes every hard rule but breaks these soft rules:</p>
      <ul className="small">{approval.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
      <h4>Plan</h4>
      <table>
        <thead><tr><th>Supplier</th><th>Mode</th><th>Qty</th></tr></thead>
        <tbody>
          {approval.plan.lines.map((l, i) => (
            <tr key={i}>
              <td>{l.supplier_id}</td>
              <td>{l.mode}{l.delivery_day != null ? ` · day ${l.delivery_day}` : ''}</td>
              <td><input type="number" value={qty[i]} style={{ width: 90 }}
                         onChange={(e) => setQty(qty.map((q, j) => (j === i ? Number(e.target.value) : q)))} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row" style={{ marginTop: 12 }}>
        <input placeholder="comment (sent to the agent)" value={comment} onChange={(e) => setComment(e.target.value)} style={{ flex: 1 }} />
        {edited
          ? <button className="primary" disabled={busy} onClick={() => act('edit')}>Approve edited plan</button>
          : <button className="ok" disabled={busy} onClick={() => act('approve')}>Approve</button>}
        <button className="bad" disabled={busy} onClick={() => act('reject')}>Reject</button>
      </div>
      <ErrorBox error={error} />
    </div>
  )
}
