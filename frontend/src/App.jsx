import { useEffect, useState } from 'react'
import { fetchTrailheads, searchRoutes } from './api.js'
import SearchForm from './components/SearchForm.jsx'
import RouteMap from './components/RouteMap.jsx'
import RouteList from './components/RouteList.jsx'

const DEFAULT_PARAMS = {
  trailheadId: 'htmo',
  targetDistKm: 10,
  targetGainM: 400,
  routeType: 'loop',
}

export default function App() {
  const [trailheads, setTrailheads] = useState([])
  const [params, setParams] = useState(DEFAULT_PARAMS)
  const [routes, setRoutes] = useState([])
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [trailheadInfo, setTrailheadInfo] = useState(null)

  // Load trailheads on mount
  useEffect(() => {
    fetchTrailheads()
      .then(data => {
        setTrailheads(data)
        if (data.length) setTrailheadInfo(data.find(t => t.id === DEFAULT_PARAMS.trailheadId) ?? data[0])
      })
      .catch(err => setError(err.message))
  }, [])

  // Update trailhead info when trailheadId changes
  useEffect(() => {
    const th = trailheads.find(t => t.id === params.trailheadId)
    if (th) setTrailheadInfo(th)
  }, [params.trailheadId, trailheads])

  async function handleSearch() {
    setLoading(true)
    setError(null)
    setRoutes([])
    setSelectedIndex(0)
    try {
      const data = await searchRoutes(params)
      setRoutes(data.routes)
      setTrailheadInfo(data.trailhead)
      if (data.routes.length === 0) setError('No routes found — try a different distance or trailhead.')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <header className="app-header">
        <div>
          <h1>Trail Routes</h1>
          <div className="subtitle">Larimer County · Fort Collins</div>
        </div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          {trailheads.length > 0 ? (
            <SearchForm
              trailheads={trailheads}
              params={params}
              onChange={setParams}
              onSearch={handleSearch}
              loading={loading}
            />
          ) : (
            <p className="status-msg">{error ? '' : 'Loading…'}</p>
          )}

          {error && <div className="error-msg">{error}</div>}

          <RouteList
            routes={routes}
            selectedIndex={selectedIndex}
            onSelect={setSelectedIndex}
          />
        </aside>

        <main className="map-pane">
          <RouteMap
            trailhead={trailheadInfo}
            routes={routes}
            selectedIndex={selectedIndex}
            onSelectRoute={setSelectedIndex}
          />
        </main>
      </div>
    </>
  )
}
