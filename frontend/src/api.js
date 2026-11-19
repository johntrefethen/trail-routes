export async function fetchTrailheads() {
  const res = await fetch('/api/trailheads')
  if (!res.ok) throw new Error(`Failed to fetch trailheads: ${res.status}`)
  return res.json()
}

export async function searchRoutes({ trailheadId, targetDistKm, targetGainM, routeType, maxResults = 5 }) {
  const params = new URLSearchParams({
    trailhead_id: trailheadId,
    target_dist_km: targetDistKm,
    max_results: maxResults,
    route_type: routeType,
  })
  if (targetGainM != null && targetGainM > 0) {
    params.set('target_gain_m', targetGainM)
  }
  const res = await fetch(`/api/routes/search?${params}`)
  if (!res.ok) {
    const body = await res.json().catch(() => ({}))
    throw new Error(body.detail || `Search failed: ${res.status}`)
  }
  return res.json()
}
