import { describe, expect, it } from 'vitest'
import {
  contributionText,
  displayScore,
  signalLabel,
  signalStatusLabel,
  verdictLabel,
  verdictMessage,
} from './verification'

describe('verification presentation', () => {
  it('uses clear, restrained verdict language', () => {
    expect(verdictLabel('VERIFIED')).toBe('Verified')
    expect(verdictLabel('REVIEW_REQUIRED')).toBe('Review required')
    expect(verdictMessage('VERIFIED')).toContain('meets the verification policy')
    expect(verdictMessage('FLAGGED')).toContain('contradiction or warning')
    expect(verdictMessage('INCONCLUSIVE')).toContain('not enough reliable evidence')
  })

  it('keeps signal names and states easy to scan', () => {
    expect(signalLabel('VISUAL_INERTIAL_CONSISTENCY')).toBe('Sensor & camera match')
    expect(signalLabel('CHALLENGE_COMPLETION')).toBe('Movement steps')
    expect(signalStatusLabel('PARTIAL')).toBe('Partial')
  })

  it('rounds only for display while preserving weighted contribution detail', () => {
    expect(displayScore(92.45)).toBe(92)
    expect(displayScore(null)).toBeNull()
    expect(contributionText(14.25, 15)).toBe('14.3 / 15')
  })
})
