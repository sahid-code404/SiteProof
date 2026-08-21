export function shortHash(value?: string | null, visible = 12) {
  if (!value) return '—'
  return value.length <= visible * 2 ? value : `${value.slice(0, visible)}…${value.slice(-visible)}`
}

export function integrityLabel(value: string) {
  return value.replace(/_/g, ' ')
}

export function receiptIsHealthy(signatureValid: boolean, status: string, integrityState: string) {
  return signatureValid && status === 'ISSUED' && integrityState === 'VALID'
}
