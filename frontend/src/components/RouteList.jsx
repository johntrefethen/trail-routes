import ElevationProfile from './ElevationProfile.jsx'

const ROUTE_COLORS = ['#e76f51', '#457b9d', '#2d6a4f', '#8338ec', '#fb8500']

export function routeColor(index) {
  return ROUTE_COLORS[index % ROUTE_COLORS.length]
}

export default function RouteList({ routes, selectedIndex, onSelect }) {
  if (!routes || routes.length === 0) return null

  return (
    <div className="route-list">
      <h2>{routes.length} route{routes.length > 1 ? 's' : ''} found</h2>
      {routes.map((route, i) => (
        <div
          key={i}
          className={`route-card ${i === selectedIndex ? 'selected' : ''}`}
          onClick={() => onSelect(i)}
        >
          <div className="route-card-header">
            <span className="rank" style={{ color: routeColor(i) }}>#{i + 1}</span>
            <span className="type-badge" style={{ background: routeColor(i) }}>
              {route.route_type}
            </span>
          </div>

          <div className="route-stats">
            <div className="route-stat">
              <span className="val">{route.distance_km}</span>
              <span className="unit"> km</span>
            </div>
            <div className="route-stat">
              <span className="val">↑{route.gain_m}</span>
              <span className="unit"> m</span>
            </div>
            <div className="route-stat">
              <span className="val">↓{route.loss_m}</span>
              <span className="unit"> m</span>
            </div>
          </div>

          {route.trail_names.length > 0 && (
            <div className="trail-names">
              {route.trail_names.slice(0, 4).join(' · ')}
            </div>
          )}

          <ElevationProfile profile={route.elevation_profile} />
        </div>
      ))}
    </div>
  )
}
