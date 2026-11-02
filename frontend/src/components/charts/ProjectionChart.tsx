// Stock by day for one product at one store. One measure (units), one axis.
// Bars: stock on the shelf after that day's deliveries. Red bars: sales lost that day (labelled).
// Reference lines: safety stock and storage limit (labelled directly). Hover tooltip + table view.
// Colours validated with the dataviz palette checks (light and dark).
import { useState } from 'react'
import {
  Bar, CartesianGrid, ComposedChart, LabelList, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import type { Projection } from '../../types/api'

const fmtDay = (iso: string) =>
  new Date(iso + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'short', day: 'numeric', month: 'short' })

interface Row {
  date: string
  label: string
  stock: number
  lost: number
  received: number
  close: number
  limit: number
}

function TooltipBox({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  if (!active || !payload?.length) return null
  const r = payload[0].payload
  return (
    <div className="tooltip">
      <strong>{r.label}</strong>
      <div>On the shelf after deliveries: {r.stock}</div>
      {r.received > 0 && <div>Delivered: {r.received}</div>}
      <div>End of day: {r.close}</div>
      {r.lost > 0 && <div style={{ color: 'var(--bad)' }}>Lost sales: {r.lost}</div>}
      <div className="muted">Storage limit: {r.limit}</div>
    </div>
  )
}

export function ProjectionChart({ projection, title, note }: { projection: Projection; title: string; note?: string }) {
  const [asTable, setAsTable] = useState(false)
  const rows: Row[] = projection.days.map((d) => ({
    date: d.date, label: fmtDay(d.date), stock: Math.round(d.available), lost: Math.round(d.lost),
    received: Math.round(d.receipts ?? 0), close: Math.round(d.close),
    limit: Math.round(d.free_l),
  }))
  const anyLost = rows.some((r) => r.lost > 0)
  const ss = projection.safety_stock

  return (
    <figure style={{ margin: 0 }}>
      <div className="chart-head">
        <h2>{title}</h2>
        <span className="spacer" />
        <button className="link" onClick={() => setAsTable(!asTable)}>{asTable ? 'Show as chart' : 'Show as table'}</button>
      </div>
      {note && <p className="muted small" style={{ marginBottom: 8 }}>{note}</p>}
      {asTable ? (
        <div className="table-wrap">
          <table>
            <thead><tr><th>Day</th><th className="num">Delivered</th><th className="num">On shelf</th><th className="num">End of day</th>
              <th className="num">Lost sales</th><th className="num">Storage limit</th></tr></thead>
            <tbody>{rows.map((r) => (
              <tr key={r.date}><td>{r.label}</td><td className="num">{r.received || ''}</td><td className="num">{r.stock}</td>
                <td className="num">{r.close}</td><td className="num">{r.lost || ''}</td><td className="num">{r.limit}</td></tr>))}</tbody>
          </table>
        </div>
      ) : (
        <>
          <div className="chart-key" aria-hidden>
            <span><i style={{ background: 'var(--series-stock)' }} />Stock on the shelf</span>
            {anyLost && <span><i style={{ background: 'var(--series-lost)' }} />Lost sales</span>}
            <span><i className="line" />Safety stock ({ss})</span>
            <span><i className="limit" />Storage limit</span>
          </div>
          <ResponsiveContainer width="100%" height={260}>
            <ComposedChart data={rows} margin={{ top: 22, right: 8, bottom: 0, left: -8 }} barGap={2} barCategoryGap="22%">
              <CartesianGrid vertical={false} stroke="var(--rule)" />
              <XAxis dataKey="label" tick={{ fontSize: 12, fill: 'var(--ink-2)' }} tickLine={false} axisLine={{ stroke: 'var(--rule-strong)' }}
                     interval="preserveStartEnd" />
              <YAxis tick={{ fontSize: 12, fill: 'var(--ink-2)' }} tickLine={false} axisLine={false} width={48} />
              <Tooltip content={<TooltipBox />} cursor={{ fill: 'var(--rule)', opacity: 0.4 }} />
              <ReferenceLine y={ss} stroke="var(--ink-2)" strokeDasharray="5 4" strokeWidth={1.5} />
              <Line dataKey="limit" type="stepAfter" stroke="var(--bad)" strokeDasharray="2 3" strokeWidth={1.5} dot={false}
                    activeDot={false} isAnimationActive={false} />
              <Bar dataKey="stock" fill="var(--series-stock)" radius={[4, 4, 0, 0]} isAnimationActive={false}>
                <LabelList dataKey="received" position="top" fontSize={11} fill="var(--ink-2)"
                           formatter={(v: number) => (v > 0 ? `+${v}` : '')} />
              </Bar>
              {anyLost && <Bar dataKey="lost" fill="var(--series-lost)" radius={[4, 4, 0, 0]} isAnimationActive={false} />}
            </ComposedChart>
          </ResponsiveContainer>
          <p className="muted small">Numbers above bars are deliveries arriving that day.</p>
        </>
      )}
    </figure>
  )
}
