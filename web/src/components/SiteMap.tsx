import { useEffect } from 'react'
import { Circle, CircleMarker, MapContainer, TileLayer, useMap, useMapEvents } from 'react-leaflet'

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

function Recenter({ latitude, longitude }: { latitude: number; longitude: number }) {
  const map = useMap()
  useEffect(() => {
    map.setView([latitude, longitude], map.getZoom())
  }, [latitude, longitude, map])
  return null
}

export function SiteMap({ latitude, longitude, radius, editable = false, onChange }: Props) {
  return (
    <MapContainer center={[latitude, longitude]} zoom={16} scrollWheelZoom className="site-map">
      <TileLayer
        attribution='&copy; OpenStreetMap contributors'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      <Recenter latitude={latitude} longitude={longitude} />
      {editable && <ClickHandler onChange={onChange} />}
      {radius ? <Circle center={[latitude, longitude]} radius={radius} pathOptions={{ weight: 1 }} /> : null}
      <CircleMarker center={[latitude, longitude]} radius={8} pathOptions={{ weight: 3 }} />
    </MapContainer>
  )
}
