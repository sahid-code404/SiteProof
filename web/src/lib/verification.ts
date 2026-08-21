import type {
  VerificationSignalStatus,
  VerificationSignalType,
  VerificationVerdict,
} from './verificationApi'

export function verdictLabel(verdict: VerificationVerdict) {
  return {
    VERIFIED: '✓ VERIFIED',
    REVIEW_REQUIRED: '⚠ REVIEW REQUIRED',
    FLAGGED: '⚠ FLAGGED',
    INCONCLUSIVE: '? INCONCLUSIVE',
  }[verdict]
}

export function verdictMessage(verdict: VerificationVerdict) {
  return {
    VERIFIED: 'Evidence strongly satisfies the configured SiteProof policy.',
    REVIEW_REQUIRED: 'Some signals require human review.',
    FLAGGED: 'Strong contradictory evidence was detected.',
    INCONCLUSIVE: 'Insufficient reliable evidence was available.',
  }[verdict]
}

export function signalLabel(type: VerificationSignalType) {
  return {
    LOCATION: 'Location',
    SESSION_TIME: 'Session / Time',
    CHALLENGE_COMPLETION: 'Random Challenges',
    SENSOR_QUALITY: 'Sensor Evidence',
    VISUAL_MOTION: 'Visual Evidence',
    SCENE_CONTINUITY: 'Scene Continuity',
    VISUAL_INERTIAL_CONSISTENCY: 'Camera ↔ Sensor Consistency',
  }[type]
}

export function signalStatusLabel(status: VerificationSignalStatus) {
  return {
    PASS: '✓ PASS',
    PARTIAL: '⚠ PARTIAL',
    FAIL: '✕ FAIL',
    INCONCLUSIVE: '? INCONCLUSIVE',
    UNAVAILABLE: '— UNAVAILABLE',
  }[status]
}

export function displayScore(score?: number | null) {
  return typeof score === 'number' ? Math.round(score) : null
}

export function contributionText(contribution: number, weight: number) {
  return `${contribution.toFixed(1)} / ${weight.toFixed(0)}`
}
