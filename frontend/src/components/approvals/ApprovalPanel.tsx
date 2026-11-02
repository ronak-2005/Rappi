// A buyer approves, rejects or edits a plan that broke a soft rule. Edited plans are re-checked against hard rules.
import { useState } from 'react'
import { writeApi } from '../../api/write'
import type { Approval } from '../../types/api'
import { ErrorBox } from '../common/ErrorBox'

export function ApprovalPanel({ approval, names = {}, onDone }: { approval: Approval; names?: Record<string, string>; onDone: () => void }) {
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
    <section className="approval" aria-live="polite">
      <h2>Your approval is needed</h2>
      <p>The plan passes every hard rule but breaks:</p>
      <ul>{approval.reasons.map((r) => <li key={r}>{r.replace(/^[a-z_]+: /, (m) => m.replaceAll('_', ' '))}</li>)}</ul>
      <table style={{ maxWidth: 520 }}>
        <thead><tr><th>Supplier</th><th>Delivery</th><th className="num">Quantity</th></tr></thead>
        <tbody>
          {approval.plan.lines.map((l, i) => (
            <tr key={i}>
              <td>{names[l.supplier_id] ?? l.supplier_id}</td>
              <td>{l.mode === 'express' ? 'Express' : 'Standard'}{l.delivery_day != null ? `, day +${l.delivery_day}` : ''}</td>
              <td className="num"><input type="number" aria-label={`Quantity for line ${i + 1}`} value={qty[i]} style={{ width: 96, textAlign: 'right' }}
                         onChange={(e) => setQty(qty.map((q, j) => (j === i ? Number(e.target.value) : q)))} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <div className="row" style={{ marginTop: 14 }}>
        <input placeholder="Note for the agent (optional)" aria-label="Note for the agent" value={comment}
               onChange={(e) => setComment(e.target.value)} style={{ flex: '1 1 260px' }} />
        <button className="primary" disabled={busy} onClick={() => act(edited ? 'edit' : 'approve')}>
          {edited ? 'Approve with my changes' : 'Approve plan'}
        </button>
        <button className="danger" disabled={busy} onClick={() => act('reject')}>Reject plan</button>
      </div>
      <ErrorBox error={error} />
    </section>
  )
}
