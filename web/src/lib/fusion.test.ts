import { describe, expect, it } from 'vitest'
import { consistencyLabel, curvePath, fusionAnalysisLabel } from './fusion'

describe('Phase 6 fusion presentation helpers', () => {
  it('handles missing motion curves without invalid SVG values', () => {
    expect(curvePath([])).toBe('')
    expect(curvePath([{ timeMs: Number.NaN, value: 1 }])).toBe('')
  })

  it('creates a finite SVG path for normalized curves', () => {
    const path = curvePath([
      { timeMs: 1000, value: 0 },
      { timeMs: 1100, value: 0.7 },
      { timeMs: 1200, value: 1 },
    ])
    expect(path.startsWith('M ')).toBe(true)
    expect(path).toContain('L ')
    expect(path).not.toContain('NaN')
    expect(path).not.toContain('Infinity')
  })

  it('renders phase-specific status wording without a final authenticity verdict', () => {
    expect(consistencyLabel('CONSISTENT')).toContain('CONSISTENT')
    expect(consistencyLabel('MISMATCH')).toContain('MISMATCH')
    expect(fusionAnalysisLabel('PENDING')).toContain('Waiting')
    expect(fusionAnalysisLabel('COMPLETE')).toContain('complete')
  })
})
