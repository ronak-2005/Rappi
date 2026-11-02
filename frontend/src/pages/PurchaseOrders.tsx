// Every purchase order in the loaded store data: ones that already existed and ones the agent placed.
import { useEffect, useState } from 'react'
import { readApi } from '../api/read'
import { Badge } from '../components/common/Badge'
import { ErrorBox } from '../components/common/ErrorBox'
import type { PurchaseOrder } from '../types/api'

const day = (iso: string) => new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })

export function PurchaseOrders() {
  const [pos, setPos] = useState<PurchaseOrder[] | null>(null)
  const [error, setError] = useState<string | null>(null)
  useEffect(() => { readApi.purchaseOrders().then(setPos).catch((e) => setError(e.message)) }, [])
  return (
    <>
      <div className="intro"><h1>Orders</h1><p className="muted">Orders for the situation currently loaded.</p></div>
      <ErrorBox error={error} />
      {pos && !pos.length && <p className="muted">No orders yet. Run a situation to see what the agent orders.</p>}
      {pos && pos.length > 0 && (
        <div className="table-wrap"><table>
          <thead><tr><th>Order</th><th>Store</th><th>Product</th><th>Supplier</th><th className="num">Ordered</th>
            <th className="num">Confirmed</th><th>Arrives</th><th>Placed by</th><th>Status</th></tr></thead>
          <tbody>{pos.map((p) => (
            <tr key={p.id}>
              <td>{p.id}</td><td>{p.node_id}</td><td>{p.sku_id}</td><td>{p.supplier_id}</td>
              <td className="num">{p.qty_ordered}</td><td className="num">{p.qty_confirmed ?? '—'}</td><td>{day(p.expected_delivery)}</td>
              <td>{p.run_id ? <a href={`#/runs/${p.run_id}`}>Agent</a> : 'Existing'}</td>
              <td><Badge value={p.status} /></td>
            </tr>))}</tbody>
        </table></div>
      )}
    </>
  )
}
