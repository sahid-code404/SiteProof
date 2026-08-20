import { describe, expect, it } from 'vitest'
import { normalizeGeocodingResult } from './geocoding'

describe('normalizeGeocodingResult', () => {
  it('normalizes coordinates and a readable name', () => {
    const result = normalizeGeocodingResult({
      lat: '22.591020',
      lon: '88.497626',
      display_name: 'Test Road, Kolkata, West Bengal, India',
      address: { road: 'Test Road', city: 'Kolkata' },
    })
    expect(result.latitude).toBeCloseTo(22.59102)
    expect(result.longitude).toBeCloseTo(88.497626)
    expect(result.name).toBe('Test Road')
    expect(result.address).toContain('Kolkata')
  })

  it('rejects invalid coordinate payloads', () => {
    expect(() => normalizeGeocodingResult({
      lat: 'not-a-number',
      lon: '88.4',
      display_name: 'Invalid',
    })).toThrow('invalid coordinates')
  })
})
