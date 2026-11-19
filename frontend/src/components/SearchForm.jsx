export default function SearchForm({ trailheads, params, onChange, onSearch, loading }) {
  const { trailheadId, targetDistKm, targetGainM, routeType } = params

  function set(key, value) {
    onChange({ ...params, [key]: value })
  }

  return (
    <form
      className="search-form"
      onSubmit={e => { e.preventDefault(); onSearch() }}
    >
      <h2>Find a Route</h2>

      <div className="form-group">
        <label>Trailhead</label>
        <select value={trailheadId} onChange={e => set('trailheadId', e.target.value)}>
          {trailheads.map(th => (
            <option key={th.id} value={th.id}>{th.name}</option>
          ))}
        </select>
      </div>

      <div className="form-group">
        <label>Target distance</label>
        <div className="slider-row">
          <input
            type="range" min={2} max={40} step={0.5}
            value={targetDistKm}
            onChange={e => set('targetDistKm', parseFloat(e.target.value))}
          />
          <span className="slider-val">{targetDistKm} km</span>
        </div>
      </div>

      <div className="form-group">
        <label>Target gain (optional)</label>
        <div className="slider-row">
          <input
            type="range" min={0} max={1500} step={25}
            value={targetGainM}
            onChange={e => set('targetGainM', parseInt(e.target.value, 10))}
          />
          <span className="slider-val">{targetGainM > 0 ? `${targetGainM} m` : 'any'}</span>
        </div>
      </div>

      <div className="form-group">
        <label>Route type</label>
        <div className="toggle-group">
          {['loop', 'out-and-back'].map(t => (
            <button
              key={t} type="button"
              className={routeType === t ? 'active' : ''}
              onClick={() => set('routeType', t)}
            >
              {t === 'loop' ? 'Loop' : 'Out & Back'}
            </button>
          ))}
        </div>
      </div>

      <button className="btn-search" disabled={loading}>
        {loading ? 'Searching…' : 'Search'}
      </button>
    </form>
  )
}
