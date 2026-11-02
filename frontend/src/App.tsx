// App shell with hash routing (static hosting friendly): #/ · #/runs/:id · #/orders · #/evals
import { useEffect, useState } from 'react'
import { readApi } from './api/read'
import { Evals } from './pages/Evals'
import { PurchaseOrders } from './pages/PurchaseOrders'
import { RunView } from './pages/RunView'
import { ScenarioLauncher } from './pages/ScenarioLauncher'

function useHash() {
  const [hash, setHash] = useState(window.location.hash || '#/')
  useEffect(() => {
    const on = () => setHash(window.location.hash || '#/')
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return [hash, (h: string) => { window.location.hash = h }] as const
}

export default function App() {
  const [hash, go] = useHash()
  const [world, setWorld] = useState<string>('')
  useEffect(() => {
    readApi.world().then((w) => setWorld(`${w.fixture_id} · today ${w.today} (${w.weekday})`)).catch(() => setWorld('no scenario loaded'))
  }, [hash])

  const runMatch = hash.match(/^#\/runs\/(.+)$/)
  const page = runMatch ? <RunView runId={runMatch[1]} />
    : hash === '#/orders' ? <PurchaseOrders />
    : hash === '#/evals' ? <Evals />
    : <ScenarioLauncher go={go} />
  const active = (h: string) => (hash === h || (h === '#/' && !!runMatch) ? 'active' : '')

  return (
    <div className="shell">
      <header className="topbar">
        <div className="brand">AI Purchasing <span>Agent</span></div>
        <nav className="nav">
          <a href="#/" className={active('#/')}>Scenarios &amp; runs</a>
          <a href="#/orders" className={active('#/orders')}>Purchase orders</a>
          <a href="#/evals" className={active('#/evals')}>Evaluation</a>
        </nav>
        <div className="world">{world}</div>
      </header>
      {page}
    </div>
  )
}
