import { describe, expect, it } from 'vitest'
import { integrityLabel, receiptIsHealthy, shortHash } from './receipt'

describe('Phase 8 receipt presentation helpers', () => {
  it('shortens long digests without hiding both ends', () => {
    expect(shortHash('a'.repeat(64), 6)).toBe('aaaaaa…aaaaaa')
  })

  it('keeps lifecycle status separate from cryptographic validity', () => {
    expect(receiptIsHealthy(true, 'ISSUED', 'VALID')).toBe(true)
    expect(receiptIsHealthy(true, 'REVOKED', 'REVOKED')).toBe(false)
  })

  it('renders machine states as readable labels', () => {
    expect(integrityLabel('INVALID_SIGNATURE')).toBe('INVALID SIGNATURE')
  })
})
