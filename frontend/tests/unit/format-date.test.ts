import { describe, expect, it } from 'vitest'

import { formatDate } from '../../src/lib/format-date'

describe('formatDate', () => {
  it('formats an ISO string in Korean long date style', () => {
    expect(formatDate('2026-11-03T12:00:00Z')).toBe('2026년 11월 3일')
  })

  it('accepts a Date', () => {
    expect(formatDate(new Date('2026-01-05T12:00:00Z'))).toBe('2026년 1월 5일')
  })

  it('treats a timestamp without a timezone as UTC', () => {
    expect(formatDate('2026-11-03T12:00:00')).toBe('2026년 11월 3일')
  })
})
