import { describe, expect, it } from 'vitest'
import {
  roundedSiteProofScore,
  scoreContribution,
  verificationSignalLabel,
  verificationVerdictDescription,
  verificationVerdictLabel,
} from './verification'


describe('Phase 7 verification presentation', () => {
  it('uses precise non-overconfident verdict language', () => {
    expect(verificationVerdictLabel('VERIFIED')).toBe('✓ VERIFIED')
    expect(verificationVerdictLabel('REVIEW_REQUIRED')).toBe('⚠ REVIEW REQUIRED')
    expect(verificationVerdictLabel('FLAGGED')).toBe('⚠ FLAGGED')
    expect(verificationVerdictLabel('INCONCLUSIVE')).toBe('? INCONCLUSIVE')
    expect(verificationVerdictDescription('VERIFIED')).not.toMatch(/100%|genuine|definitely/i)
    expect(verificationVerdictDescription('FLAGGED')).not.toMatch(/fraud|fake|attacker/i)
  })

  it('formats score contribution without changing stored precision', () => {
    expect(roundedSiteProofScore(92.45)).toBe(92)
    expect(scoreContribution(14.25, 15)).toBe('14.3 / 15.0')
  })

  it('labels cross-signal evidence separately', () => {
    expect(verificationSignalLabel('VISUAL_INERTIAL_CONSISTENCY')).toContain('Sensor')
  })
})
