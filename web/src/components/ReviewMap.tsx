import { useEffect } from 'react'
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from 'react-leaflet'
import { Link } from 'react-router-dom'
import type { ReviewQueueItem } from '../lib/verificationApi'

type Props = {
  items: ReviewQueueItem[]
  selectedId?: string | null
  onSelect?: (inspectionId: string) => void
}

function FitReviewBounds({ items }: { items: ReviewQueueItem[] }) {
  const map = useMap()

  useEffect(() => {
    if (!items.length) return
    if (items.length === 1) {
      map.setView([items[0].latitude, items[0].longitude], 16)
      return
    }
    map.fitBounds(items.map((item) => [item.latitude, item.longitude] as [number, number]), {
      padding: [28, 28],
      maxZoom: 15,
    })
  }, [items, map])

  return null
}

function scoreText(value?: number | null) {
  return typeof value === 'number' ? value.toFixed(2) : '—'
}

function confidenceText(value?: number | null) {
  return typeof value === 'number' ? `${Math.round(value * 100)}%` : '—'
}

function capturedText(value?: string | null) {
  if (!value) return 'Capture time unavailable'
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value))
}

export function ReviewMap({ items, selectedId, onSelect }: Props) {
  const first = items[0]
  const center: [number, number] = first ? [first.latitude, first.longitude] : [20.5937, 78.9629]

  return (
    <div className="review-map-region" role="region" aria-label="Verification site map">
      <p className="sr-only">Use the evidence queue beside this map for keyboard-accessible site selection and navigation.</p>
      <MapContainer center={center} zoom={5} scrollWheelZoom className="review-map">
        <TileLayer
          attribution='&copy; OpenStreetMap contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        <FitReviewBounds items={items} />
        {items.map((item) => {
          const selected = item.inspectionId === selectedId
          return (
            <CircleMarker
              key={item.inspectionId}
              center={[item.latitude, item.longitude]}
              radius={selected ? 10 : 7}
              pathOptions={{ weight: selected ? 4 : 2, fillOpacity: selected ? 0.9 : 0.7 }}
              eventHandlers={{ click: () => onSelect?.(item.inspectionId) }}
            >
              <Popup>
                <div className="review-map-popup">
                  <strong>{item.title}</strong>
                  <span>{item.locationName || item.locationAddress || 'Unnamed site'}</span>
                  <span>Inspector: {item.inspectorName || 'Unassigned'}</span>
                  <span>Captured: {capturedText(item.captureEndedAt)}</span>
                  <span>{item.verdict.replace(/_/g, ' ')} · score {scoreText(item.score)} · confidence {confidenceText(item.confidence)}</span>
                  <Link to={`/inspections/${item.inspectionId}`}>Open evidence</Link>
                </div>
              </Popup>
            </CircleMarker>
          )
        })}
      </MapContainer>
    </div>
  )
}
