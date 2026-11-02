// Day-by-day stock (bars) against safety stock and free storage (lines): what the agent saw / what happened.
import { Bar, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { Projection } from '../../types/api'

export function ProjectionChart({ projection, unitVolume = 1 }: { projection: Projection; unitVolume?: number }) {
  const data = projection.days.map((d) => ({
    date: d.date.slice(5),
    'stock (peak)': d.available,
    'end of day': d.close,
    'lost sales': d.lost || null,
    'safety stock': projection.safety_stock,
    'free storage': Math.round(d.free_l / unitVolume),
  }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -12 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
        <XAxis dataKey="date" tick={{ fontSize: 11, fill: 'var(--muted)' }} />
        <YAxis tick={{ fontSize: 11, fill: 'var(--muted)' }} />
        <Tooltip contentStyle={{ background: 'var(--panel)', border: '1px solid var(--border)', fontSize: 12 }} />
        <Legend wrapperStyle={{ fontSize: 12 }} />
        <Bar dataKey="stock (peak)" fill="#7da2ff" radius={[3, 3, 0, 0]} />
        <Bar dataKey="lost sales" fill="#f07070" radius={[3, 3, 0, 0]} />
        <Line dataKey="end of day" stroke="#2f5bd3" dot={false} strokeWidth={2} />
        <Line dataKey="safety stock" stroke="#f0b04a" dot={false} strokeDasharray="6 4" />
        <Line dataKey="free storage" stroke="#c62e2e" dot={false} strokeDasharray="2 3" />
      </ComposedChart>
    </ResponsiveContainer>
  )
}
