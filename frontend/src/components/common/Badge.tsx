const TONE: Record<string, string> = {
  completed: 'ok', OK: 'ok', confirmed: 'ok', accept: 'ok', approved: 'ok', received: 'ok', passed: 'ok',
  awaiting_approval: 'warn', DEGRADED_OK: 'warn', partially_confirmed: 'warn', modify: 'warn', pending: 'warn', edited: 'warn',
  investigate: 'warn',
  failed: 'bad', UNACCEPTABLE: 'bad', rejected: 'bad', reject: 'bad', escalated: 'bad', escalate: 'bad', cancelled: 'neutral',
}

export function Badge({ value, tone }: { value: string | null | undefined; tone?: string }) {
  if (!value) return null
  return <span className={`badge ${tone ?? TONE[value] ?? ''}`}>{value.replaceAll('_', ' ')}</span>
}
