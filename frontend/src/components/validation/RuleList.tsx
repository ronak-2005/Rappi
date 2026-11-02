// The rulebook's verdict. Problems first; passing rules collapse into one line.
import { useState } from 'react'

interface Rule { rule: string; kind: string; passed: boolean; message: string }

export function RuleList({ results }: { results: Rule[] }) {
  const [showAll, setShowAll] = useState(false)
  const problems = results.filter((r) => !r.passed)
  const passing = results.filter((r) => r.passed)
  const row = (r: Rule) => (
    <li key={r.rule}>
      <span className={`mark ${r.passed ? 'pass' : r.kind === 'hard' ? 'fail' : 'ask'}`} aria-hidden>{r.passed ? '✓' : r.kind === 'hard' ? '✕' : '!'}</span>
      <span>{r.rule.replaceAll('_', ' ')}<br /><span className="kind">{r.kind === 'hard' ? 'hard rule' : 'needs approval if broken'}</span></span>
      <span className="muted">{r.passed ? r.message : `${r.kind === 'hard' ? 'Blocked' : 'Needs approval'}: ${r.message}`}</span>
    </li>
  )
  return (
    <div>
      {problems.length > 0 && <ul className="rules">{problems.map(row)}</ul>}
      <p className="small" style={{ margin: '8px 0' }}>
        <span className="status ok">{passing.length} of {results.length} rules passed</span>{' '}
        <button className="link small" onClick={() => setShowAll(!showAll)}>{showAll ? 'Hide' : 'Show them'}</button>
      </p>
      {showAll && <ul className="rules">{passing.map(row)}</ul>}
    </div>
  )
}
