// Status words. Colour always comes with the word itself (never colour alone).
import { capitalize, humanize } from '../../format'

const TONE: Record<string, 'ok' | 'warn' | 'bad' | 'neutral'> = {
  completed: 'ok', OK: 'ok', confirmed: 'ok', approved: 'ok', received: 'ok', passed: 'ok', accept: 'ok',
  awaiting_approval: 'warn', DEGRADED_OK: 'warn', partially_confirmed: 'warn', pending: 'warn', edited: 'warn',
  modify: 'warn', investigate: 'warn', running: 'neutral', in_transit: 'neutral', sent: 'neutral',
  failed: 'bad', UNACCEPTABLE: 'bad', rejected: 'bad', reject: 'bad', escalated: 'bad', escalate: 'bad',
  cancelled: 'neutral',
}
const WORDS: Record<string, string> = {
  OK: 'Verified OK', DEGRADED_OK: 'OK with differences', UNACCEPTABLE: 'Not acceptable',
  awaiting_approval: 'Waiting for approval', partially_confirmed: 'Partly confirmed', in_transit: 'In transit',
}

export function Badge({ value, tone }: { value: string | null | undefined; tone?: 'ok' | 'warn' | 'bad' | 'neutral' }) {
  if (!value) return null
  const word = WORDS[value] ?? capitalize(humanize(value))
  return <span className={`status ${tone ?? TONE[value] ?? 'neutral'}`}>{word}</span>
}
