import { useEffect } from 'react'
import { MapContainer, TileLayer, Polyline, Marker, Popup, useMap } from 'react-leaflet'
import L from 'leaflet'
import 'leaflet/dist/leaflet.css'

// Fix Leaflet's default icon path broken by bundlers
delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
})

const ROUTE_COLORS = ['#e76f51', '#457b9d', '#2d6a4f', '#8338ec', '#fb8500']

/** Fit map to the selected route whenever it changes. */
function FitBounds({ routes, selectedIndex }) {
  const map = useMap()
  useEffect(() => {
    const route = routes?.[selectedIndex] ?? routes?.[0]
    if (!route?.coords?.length) return
    const bounds = L.latLngBounds(route.coords.map(([lat, lon]) => [lat, lon]))
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [32, 32] })
  }, [map, routes, selectedIndex])
  return null
}

export default function RouteMap({ trailhead, routes, selectedIndex, onSelectRoute }) {
  const center = trailhead
    ? [trailhead.lat, trailhead.lon]
    : [40.55, -105.17]

  return (
    <MapContainer
      center={center}
      zoom={13}
      style={{ width: '100%', height: '100%', minHeight: 400 }}
    >
      <TileLayer
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        maxZoom={19}
      />

      {routes?.map((route, i) => (
        <Polyline
          key={i}
          positions={route.coords.map(([lat, lon]) => [lat, lon])}
          pathOptions={{
            color: ROUTE_COLORS[i % ROUTE_COLORS.length],
            weight: i === selectedIndex ? 5 : 2.5,
            opacity: i === selectedIndex ? 1 : 0.55,
          }}
          eventHandlers={{ click: () => onSelectRoute(i) }}
        />
      ))}

      {trailhead && (
        <Marker position={[trailhead.node_lat, trailhead.node_lon]}>
          <Popup>{trailhead.name}</Popup>
        </Marker>
      )}

      {routes?.length > 0 && (
        <FitBounds routes={routes} selectedIndex={selectedIndex} />
      )}
    </MapContainer>
  )
}
