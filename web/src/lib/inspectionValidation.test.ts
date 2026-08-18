import { describe, expect, it } from 'vitest'
import { validateInspectionInput } from './inspectionValidation'

const future = new Date(Date.now() + 60_000).toISOString()

function valid(overrides: Partial<Parameters<typeof validateInspectionInput>[0]> = {}) {
  return validateInspectionInput({
    title: 'Verify repaired pothole',
    latitude: 22.5726,
    longitude: 88.3639,
    radius: 100,
    deadline: future,
    ...overrides,
  })
}

describe('inspection form validation', () => {
  it('accepts a valid inspection', () => expect(valid()).toBeNull())
  it('rejects invalid latitude', () => expect(valid({ latitude: 91 })).toContain('Latitude'))
  it('rejects invalid longitude', () => expect(valid({ longitude: -181 })).toContain('Longitude'))
  it('rejects invalid radius', () => expect(valid({ radius: 9 })).toContain('radius'))
  it('rejects past deadline', () => expect(valid({ deadline: '2020-01-01T00:00:00Z' })).toContain('future'))
})
