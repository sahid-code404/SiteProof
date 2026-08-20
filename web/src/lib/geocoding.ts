export type GeocodingResult = {
  latitude: number
  longitude: number
  displayName: string
  name: string
  address: string
}

type NominatimAddress = Record<string, string | undefined>

type NominatimResult = {
  lat: string
  lon: string
  display_name: string
  name?: string
  address?: NominatimAddress
}

function readableName(item: NominatimResult): string {
  const address = item.address ?? {}
  return item.name
    ?? address.road
    ?? address.neighbourhood
    ?? address.suburb
    ?? address.city
    ?? address.town
    ?? address.village
    ?? item.display_name.split(',')[0]?.trim()
    ?? 'Selected location'
}

export function normalizeGeocodingResult(item: NominatimResult): GeocodingResult {
  const latitude = Number(item.lat)
  const longitude = Number(item.lon)
  if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
    throw new Error('Location service returned invalid coordinates.')
  }
  return {
    latitude,
    longitude,
    displayName: item.display_name,
    name: readableName(item),
    address: item.display_name,
  }
}

async function nominatim(url: URL, fetcher: typeof fetch = fetch): Promise<unknown> {
  const response = await fetcher(url.toString(), {
    headers: { Accept: 'application/json' },
  })
  if (!response.ok) throw new Error(`Location search failed (${response.status}).`)
  return response.json()
}

export async function searchLocation(query: string, fetcher: typeof fetch = fetch): Promise<GeocodingResult[]> {
  const trimmed = query.trim()
  if (trimmed.length < 3) throw new Error('Enter at least 3 characters to search.')
  const url = new URL('https://nominatim.openstreetmap.org/search')
  url.searchParams.set('q', trimmed)
  url.searchParams.set('format', 'jsonv2')
  url.searchParams.set('addressdetails', '1')
  url.searchParams.set('limit', '5')
  const body = await nominatim(url, fetcher)
  if (!Array.isArray(body)) throw new Error('Location search returned an unexpected response.')
  return body.map((item) => normalizeGeocodingResult(item as NominatimResult))
}

export async function reverseLocation(
  latitude: number,
  longitude: number,
  fetcher: typeof fetch = fetch,
): Promise<GeocodingResult | null> {
  const url = new URL('https://nominatim.openstreetmap.org/reverse')
  url.searchParams.set('lat', String(latitude))
  url.searchParams.set('lon', String(longitude))
  url.searchParams.set('format', 'jsonv2')
  url.searchParams.set('addressdetails', '1')
  const body = await nominatim(url, fetcher)
  if (!body || Array.isArray(body)) return null
  return normalizeGeocodingResult(body as NominatimResult)
}
