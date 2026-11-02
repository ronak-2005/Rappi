// Every purchase order in the loaded world (pre-existing ones and the agent's), with supplier events.
import { useEffect, useState } from 'react'
import { readApi } from '../api/read'
import { Badge } from '../components/common/Badge'
import { ErrorBox } from '../components/common/ErrorBox'
import type { PurchaseOrder } from '../types/api'

export function PurchaseOrders() {
  const [pos, setPos] = useState<PurchaseOrder[]>([])
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { readApi.purchaseOrders().then(setPos).catch((e) => setError(e.message)) }, [])
  return (
    <div className="card">
      <ErrorBox error={error} />
      <h3>Purchase orders</h3>
      <div className="table-wrap"><table>
        <thead><tr><th>PO</th><th>Store</th><th>SKU</th><th>Supplier</th><th>Ordered</th><th>Confirmed</th><th>Delivery</th>
          <th>By</th><th>Status</th><th>Events</th></tr></thead>
        <tbody>{pos.map((p) => (
          <tr key={p.id}>
            <td className="mono">{p.id}</td><td>{p.node_id}</td><td>{p.sku_id}</td><td>{p.supplier_id}</td>
            <td>{p.qty_ordered}</td><td>{p.qty_confirmed ?? '—'}</td><td>{p.expected_delivery}</td>
            <td>{p.run_id ? <a href={`#/runs/${p.run_id}`}>agent</a> : p.created_by}</td>
            <td><Badge value={p.status} /></td>
            <td className="small muted">{(p.events ?? []).map((e) => e.type).join(' → ')}</td>
          </tr>))}</tbody>
      </table></div>
    </div>
  )
}
