import { describe, expect, it } from 'vitest'

import { complexityLabel, formatFileSize } from '../../src/lib/task-labels'

describe('formatFileSize', () => {
  it.each([
    [0, '0 B'],
    [1023, '1023 B'],
    [1536, '1.5 KB'],
    [5 * 1024 * 1024, '5.0 MB'],
  ])('formats %i bytes as %s', (bytes, text) => {
    expect(formatFileSize(bytes)).toBe(text)
  })
})

describe('complexityLabel', () => {
  it('names the three levels in Korean', () => {
    expect(
      (['beginner', 'intermediate', 'advanced'] as const).map((level) => complexityLabel(level)),
    ).toEqual(['초급', '중급', '고급'])
  })
})
