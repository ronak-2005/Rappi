// The rulebook's verdict: one line per rule (hard rules block, soft rules need approval).
import { Badge } from '../common/Badge'

export function RuleList({ results }: { results: { rule: string; kind: string; passed: boolean; message: string }[] }) {
  return (
    <div>
      {results.map((r) => (
        <div className="rule" key={r.rule}>
          <span>{r.passed ? '✅' : r.kind === 'hard' ? '⛔' : '⚠️'}</span>
          <strong>{r.rule.replaceAll('_', ' ')}</strong>
          <Badge value={r.kind} tone="neutral" />
          <span className="muted">{r.message}</span>
        </div>
      ))}
    </div>
  )
}
