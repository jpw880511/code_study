import { describe, expect, it } from 'vitest'

import {
  MAX_DESCRIPTION_LENGTH,
  MAX_TITLE_LENGTH,
  validateProjectDescription,
  validateProjectTitle,
} from '../../src/lib/project-validation'

describe('validateProjectTitle', () => {
  it('requires at least one character after trimming', () => {
    expect(validateProjectTitle('')).toBe('프로젝트 제목은 최소 1자 이상이어야 합니다.')
    expect(validateProjectTitle('   ')).toBe('프로젝트 제목은 최소 1자 이상이어야 합니다.')
  })

  it('allows up to 255 characters, ignoring surrounding spaces', () => {
    expect(validateProjectTitle('a'.repeat(MAX_TITLE_LENGTH))).toBeUndefined()
    expect(validateProjectTitle(` ${'a'.repeat(MAX_TITLE_LENGTH)} `)).toBeUndefined()
    expect(validateProjectTitle('a'.repeat(MAX_TITLE_LENGTH + 1))).toBe(
      '프로젝트 제목은 최대 255자까지 입력 가능합니다.',
    )
  })
})

describe('validateProjectDescription', () => {
  it('is optional and limited to 2000 characters', () => {
    expect(validateProjectDescription('')).toBeUndefined()
    expect(validateProjectDescription('a'.repeat(MAX_DESCRIPTION_LENGTH))).toBeUndefined()
    expect(validateProjectDescription('a'.repeat(MAX_DESCRIPTION_LENGTH + 1))).toBe(
      '프로젝트 설명은 최대 2000자까지 입력 가능합니다.',
    )
  })
})
