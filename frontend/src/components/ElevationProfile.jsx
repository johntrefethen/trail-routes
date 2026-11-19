/**
 * Minimal SVG elevation profile.
 * profile: [[cumulative_dist_m, cumulative_gain_m], ...]
 */
export default function ElevationProfile({ profile }) {
  if (!profile || profile.length < 2) return null

  const W = 280, H = 54, PX = 4, PY = 6
  const maxDist = profile[profile.length - 1][0] || 1
  const gains = profile.map(p => p[1])
  const minG = Math.min(...gains)
  const maxG = Math.max(...gains)
  const range = maxG - minG || 1

  const pts = profile.map(([d, g]) => {
    const x = PX + ((d / maxDist) * (W - 2 * PX))
    const y = H - PY - (((g - minG) / range) * (H - 2 * PY))
    return `${x.toFixed(1)},${y.toFixed(1)}`
  }).join(' ')

  // Fill polygon
  const first = `${PX},${H - PY}`
  const last = `${(PX + (W - 2 * PX)).toFixed(1)},${H - PY}`
  const fill = `${first} ${pts} ${last}`

  return (
    <div className="elev-profile">
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none">
        <polygon points={fill} fill="#52b78833" />
        <polyline points={pts} fill="none" stroke="#2d6a4f" strokeWidth="1.5" />
      </svg>
    </div>
  )
}
