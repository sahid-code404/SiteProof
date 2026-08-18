import { Circle, CircleMarker, MapContainer, TileLayer, useMapEvents } from 'react-leaflet'

type Props = {
  latitude: number
  longitude: number
  radius?: number
  editable?: boolean
  onChange?: (latitude: number, longitude: number) => void
}

function ClickHandler({ onChange }: { onChange?: (latitude: number, longitude: number) => void }) {
  useMapEvents({
    click(event) {
      onChange?.(event.latlng.lat, event.latlng.lng)
    },
  })
  return null
}

export function SiteMap({ latitude, longitude, radius, editable = false, onChange }: Props) {
  return (
    <MapContainer center={[latitude, longitude]} zoom={16} scrollWheelZoom className="site-map" key={`${latitude.toFixed(3)}-${longitude.toFixed(3)}`}>
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {editable && <ClickHandler onChange={onChange} />}
      {radius ? <Circle center={[latitude, longitude]} radius={radius} pathOptions={{ weight: 1 }} /> : null}
      <CircleMarker center={[latitude, longitude]} radius={8} pathOptions={{ weight: 3 }} />
    </MapContainer>
  )
}
