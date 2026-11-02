// App shell with hash routing (works on any static host): #/ · #/runs/:id · #/orders · #/evals
import { useEffect, useState } from 'react'
import { readApi } from './api/read'
import { Evals } from './pages/Evals'
import { PurchaseOrders } from './pages/PurchaseOrders'
import { RunView } from './pages/RunView'
import { ScenarioLauncher } from './pages/ScenarioLauncher'

function useHash() {
  const [hash, setHash] = useState(window.location.hash || '#/')
  useEffect(() => {
    const on = () => { setHash(window.location.hash || '#/'); window.scrollTo(0, 0) }
    window.addEventListener('hashchange', on)
    return () => window.removeEventListener('hashchange', on)
  }, [])
  return [hash, (h: string) => { window.location.hash = h }] as const
}

export default function App() {
  const [hash, go] = useHash()
  const [world, setWorld] = useState('')
  useEffect(() => {
    readApi.world()
      .then((w) => setWorld(`Store data as of ${new Date(w.today + 'T12:00:00').toLocaleDateString('en-GB', { weekday: 'long', day: 'numeric', month: 'long' })}`))
      .catch(() => setWorld('No situation loaded yet'))
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
        <a className="brand" href="#/" style={{ color: 'inherit', textDecoration: 'none' }}>
          <img src="/favicon.svg" alt="" />Purchasing desk
        </a>
        <nav className="nav" aria-label="Main">
          <a href="#/" className={active('#/')}>Situations</a>
          <a href="#/orders" className={active('#/orders')}>Orders</a>
          <a href="#/evals" className={active('#/evals')}>Evaluation</a>
        </nav>
        <span className="world">{world}</span>
      </header>
      <main>{page}</main>
    </div>
  )
}
