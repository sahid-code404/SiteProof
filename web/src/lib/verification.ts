import type {
  VerificationSignalStatus,
  VerificationSignalType,
  VerificationVerdict,
} from './verificationApi'

export function verdictLabel(verdict: VerificationVerdict) {
  return {
    VERIFIED: 'Verified',
    REVIEW_REQUIRED: 'Review required',
    FLAGGED: 'Flagged',
    INCONCLUSIVE: 'Inconclusive',
  }[verdict]
}

export function verdictMessage(verdict: VerificationVerdict) {
  return {
    VERIFIED: 'The available evidence meets the verification policy.',
    REVIEW_REQUIRED: 'One or more signals need a reviewer to check them.',
    FLAGGED: 'The evidence contains a strong contradiction or warning.',
    INCONCLUSIVE: 'There is not enough reliable evidence for a clear result.',
  }[verdict]
}

export function signalLabel(type: VerificationSignalType) {
  return {
    LOCATION: 'Location',
    SESSION_TIME: 'Session time',
    CHALLENGE_COMPLETION: 'Movement steps',
    SENSOR_QUALITY: 'Motion sensors',
    VISUAL_MOTION: 'Camera motion',
    SCENE_CONTINUITY: 'Scene continuity',
    VISUAL_INERTIAL_CONSISTENCY: 'Sensor & camera match',
  }[type]
}

export function signalStatusLabel(status: VerificationSignalStatus) {
  return {
    PASS: 'Pass',
    PARTIAL: 'Partial',
    FAIL: 'Fail',
    INCONCLUSIVE: 'Inconclusive',
    UNAVAILABLE: 'Unavailable',
  }[status]
}

export function displayScore(score?: number | null) {
  return typeof score === 'number' ? Math.round(score) : null
}

export function contributionText(contribution: number, weight: number) {
  return `${contribution.toFixed(1)} / ${weight.toFixed(0)}`
}
