import { describe, expect, it } from 'vitest'
import {
  contributionText,
  displayScore,
  signalLabel,
  signalStatusLabel,
  verdictLabel,
  verdictMessage,
} from './verification'

describe('Phase 7 verification presentation', () => {
  it('uses precise non-overconfident verdict language', () => {
    expect(verdictLabel('VERIFIED')).toBe('✓ VERIFIED')
    expect(verdictMessage('VERIFIED')).toContain('configured SiteProof policy')
    expect(verdictMessage('FLAGGED')).toContain('contradictory evidence')
    expect(verdictMessage('INCONCLUSIVE')).toContain('Insufficient reliable evidence')
  })

  it('keeps report signal names human-readable', () => {
    expect(signalLabel('VISUAL_INERTIAL_CONSISTENCY')).toBe('Camera ↔ Sensor Consistency')
    expect(signalStatusLabel('PARTIAL')).toBe('⚠ PARTIAL')
  })

  it('rounds only for display while preserving weighted contribution detail', () => {
    expect(displayScore(92.45)).toBe(92)
    expect(displayScore(null)).toBeNull()
    expect(contributionText(14.25, 15)).toBe('14.3 / 15')
  })
})
