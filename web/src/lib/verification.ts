import type { VerificationSignalType, VerificationVerdict } from './verificationApi'

export function verificationVerdictLabel(value?: VerificationVerdict | null) {
  if (value === 'VERIFIED') return '✓ VERIFIED'
  if (value === 'REVIEW_REQUIRED') return '⚠ REVIEW REQUIRED'
  if (value === 'FLAGGED') return '⚠ FLAGGED'
  if (value === 'INCONCLUSIVE') return '? INCONCLUSIVE'
  return 'Verification pending'
}

export function verificationVerdictDescription(value?: VerificationVerdict | null) {
  if (value === 'VERIFIED') return 'Evidence strongly satisfies the configured SiteProof policy.'
  if (value === 'REVIEW_REQUIRED') return 'Some evidence requires human review.'
  if (value === 'FLAGGED') return 'Strong contradictory or failing evidence was detected.'
  if (value === 'INCONCLUSIVE') return 'Insufficient reliable evidence was available.'
  return 'Waiting for the verification engine to finish.'
}

export function verificationSignalLabel(value: VerificationSignalType) {
  return {
    LOCATION: 'Location',
    SESSION_TIME: 'Session / Time',
    CHALLENGE_COMPLETION: 'Random Challenges',
    SENSOR_EVIDENCE: 'Sensor Evidence',
    VISUAL_EVIDENCE: 'Visual Evidence',
    SCENE_CONTINUITY: 'Scene Continuity',
    VISUAL_INERTIAL_CONSISTENCY: 'Camera ↔ Sensor Consistency',
  }[value]
}

export function roundedSiteProofScore(value?: number | null) {
  return typeof value === 'number' ? Math.round(value) : null
}

export function scoreContribution(value: number, weight: number) {
  return `${value.toFixed(1)} / ${weight.toFixed(1)}`
}
