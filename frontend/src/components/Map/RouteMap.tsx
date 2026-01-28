import { useEffect, useRef } from 'react'
import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap } from 'react-leaflet'
import L from 'leaflet'
import type { PlannedVisit } from '../../types'

// Fix for default marker icons in React-Leaflet
delete (L.Icon.Default.prototype as any)._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/images/marker-shadow.png',
})

// Custom marker icon
const createNumberedIcon = (number: number) => {
  return L.divIcon({
    className: 'custom-marker',
    html: `<div style="
      background-color: #2563eb;
      color: white;
      width: 28px;
      height: 28px;
      border-radius: 50%;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 12px;
      font-weight: bold;
      border: 2px solid white;
      box-shadow: 0 2px 4px rgba(0,0,0,0.3);
    ">${number}</div>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
    popupAnchor: [0, -14],
  })
}

const agentIcon = L.divIcon({
  className: 'agent-marker',
  html: `<div style="
    background-color: #059669;
    color: white;
    width: 32px;
    height: 32px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 16px;
    border: 2px solid white;
    box-shadow: 0 2px 4px rgba(0,0,0,0.3);
  ">A</div>`,
  iconSize: [32, 32],
  iconAnchor: [16, 16],
  popupAnchor: [0, -16],
})

interface RouteMapProps {
  visits: PlannedVisit[]
  agentLocation?: { lat: number; lng: number }
}

function FitBounds({ visits, agentLocation }: RouteMapProps) {
  const map = useMap()

  useEffect(() => {
    if (visits.length === 0 && !agentLocation) return

    const points: [number, number][] = visits.map((v) => [v.latitude, v.longitude])
    if (agentLocation) {
      points.push([agentLocation.lat, agentLocation.lng])
    }

    if (points.length > 0) {
      const bounds = L.latLngBounds(points)
      map.fitBounds(bounds, { padding: [50, 50] })
    }
  }, [visits, agentLocation, map])

  return null
}

export default function RouteMap({ visits, agentLocation }: RouteMapProps) {
  // Default center: Tashkent
  const defaultCenter: [number, number] = [41.311081, 69.279737]

  const center = visits.length > 0
    ? [visits[0].latitude, visits[0].longitude] as [number, number]
    : agentLocation
      ? [agentLocation.lat, agentLocation.lng] as [number, number]
      : defaultCenter

  // Create polyline coordinates
  const routeCoordinates: [number, number][] = []
  if (agentLocation) {
    routeCoordinates.push([agentLocation.lat, agentLocation.lng])
  }
  visits.forEach((visit) => {
    routeCoordinates.push([visit.latitude, visit.longitude])
  })
  if (agentLocation && visits.length > 0) {
    routeCoordinates.push([agentLocation.lat, agentLocation.lng])
  }

  return (
    <MapContainer
      center={center}
      zoom={13}
      style={{ height: '100%', width: '100%' }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <FitBounds visits={visits} agentLocation={agentLocation} />

      {/* Agent/Depot marker */}
      {agentLocation && (
        <Marker
          position={[agentLocation.lat, agentLocation.lng]}
          icon={agentIcon}
        >
          <Popup>
            <strong>Agent Start/End Location</strong>
          </Popup>
        </Marker>
      )}

      {/* Visit markers */}
      {visits.map((visit) => (
        <Marker
          key={`${visit.client_id}-${visit.sequence_number}`}
          position={[visit.latitude, visit.longitude]}
          icon={createNumberedIcon(visit.sequence_number)}
        >
          <Popup>
            <div className="min-w-[150px]">
              <strong>{visit.client_name}</strong>
              <br />
              <span className="text-gray-600">Stop #{visit.sequence_number}</span>
              <br />
              <span className="text-sm">
                Arrival: {visit.estimated_arrival}
                <br />
                Departure: {visit.estimated_departure}
              </span>
              {visit.distance_from_previous_km > 0 && (
                <>
                  <br />
                  <span className="text-xs text-gray-500">
                    {visit.distance_from_previous_km.toFixed(1)} km from previous
                  </span>
                </>
              )}
            </div>
          </Popup>
        </Marker>
      ))}

      {/* Route line */}
      {routeCoordinates.length > 1 && (
        <Polyline
          positions={routeCoordinates}
          color="#2563eb"
          weight={3}
          opacity={0.7}
          dashArray="5, 10"
        />
      )}
    </MapContainer>
  )
}
