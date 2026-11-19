import { describe, expect, it } from 'vitest'

import {
  EXCLUDED_NOTICE,
  MAX_FILES,
  MAX_TOTAL_BYTES,
  PASTE_LANGUAGES,
  SUPPORTED_EXTENSIONS,
  splitExcluded,
  toFolderEntries,
  validatePaste,
  validateTaskDescription,
  validateTaskTitle,
  validateUploadFiles,
} from '../../src/lib/upload-validation'
import { makeFile, makeSizedFile } from '../helpers/task-fixtures'

describe('constants', () => {
  it('lists the 12 supported extensions and the paste languages with separate labels', () => {
    expect(SUPPORTED_EXTENSIONS).toEqual([
      '.py',
      '.js',
      '.ts',
      '.jsx',
      '.tsx',
      '.html',
      '.css',
      '.java',
      '.cpp',
      '.c',
      '.txt',
      '.md',
    ])
    expect(PASTE_LANGUAGES.map((l) => l.value)).toEqual([
      'python',
      'javascript',
      'typescript',
      'java',
      'c',
      'cpp',
      'html',
      'css',
      'markdown',
      'text',
    ])
    expect(PASTE_LANGUAGES.find((l) => l.value === 'cpp')?.label).toBe('C++')
    expect(MAX_TOTAL_BYTES).toBe(10 * 1024 * 1024)
    expect(MAX_FILES).toBe(20)
  })
})

describe('validateTaskTitle / validateTaskDescription', () => {
  it('requires at least 5 characters after trimming', () => {
    expect(validateTaskTitle(' 1234 ')).toBe('Task 제목은 최소 5자 이상이어야 합니다.')
    expect(validateTaskTitle('12345')).toBeUndefined()
  })

  it('allows at most 255 characters in the title', () => {
    expect(validateTaskTitle('a'.repeat(256))).toBe('Task 제목은 최대 255자까지 입력 가능합니다.')
    expect(validateTaskTitle('a'.repeat(255))).toBeUndefined()
  })

  it('allows at most 500 characters in the description', () => {
    expect(validateTaskDescription('a'.repeat(501))).toBe(
      'Task 설명은 최대 500자까지 입력 가능합니다.',
    )
    expect(validateTaskDescription('a'.repeat(500))).toBeUndefined()
    expect(validateTaskDescription('')).toBeUndefined()
  })
})

describe('validateUploadFiles', () => {
  it('asks for at least one file', () => {
    expect(validateUploadFiles([])).toBe('업로드할 파일을 선택하세요.')
  })

  it('rejects more than 20 files with the contract message', () => {
    const files = Array.from({ length: 21 }, (_, i) => makeFile(`f${i}.py`))
    expect(validateUploadFiles(files)).toBe(
      '업로드당 최대 20개 파일까지 가능합니다. 파일 수를 줄이거나 폴더 업로드를 사용하세요.',
    )
    expect(validateUploadFiles(files.slice(0, 20))).toBeUndefined()
  })

  it('rejects an unsupported extension and names it', () => {
    expect(validateUploadFiles([makeFile('virus.exe')])).toBe(
      `지원하지 않는 파일 형식입니다 (.exe). 지원 형식: ${SUPPORTED_EXTENSIONS.join(', ')}`,
    )
  })

  it('treats extensions case-insensitively and rejects files without one', () => {
    expect(validateUploadFiles([makeFile('MAIN.PY')])).toBeUndefined()
    expect(validateUploadFiles([makeFile('Makefile')])).toContain('지원하지 않는 파일 형식입니다')
  })

  it('rejects a single file over 10MB and a total over 10MB', () => {
    expect(validateUploadFiles([makeSizedFile('a.py', MAX_TOTAL_BYTES + 1)])).toBe(
      '파일 크기가 10MB를 초과합니다.',
    )
    const half = MAX_TOTAL_BYTES / 2 + 1
    expect(validateUploadFiles([makeSizedFile('a.py', half), makeSizedFile('b.py', half)])).toBe(
      '업로드한 파일의 전체 크기가 10MB를 초과합니다.',
    )
    expect(validateUploadFiles([makeSizedFile('a.py', MAX_TOTAL_BYTES)])).toBeUndefined()
  })
})

describe('splitExcluded / toFolderEntries', () => {
  it('uses webkitRelativePath as the path and falls back to the file name', () => {
    const entries = toFolderEntries([makeFile('a.py', 'x', 'app/a.py'), makeFile('b.py')])
    expect(entries.map((e) => e.path)).toEqual(['app/a.py', 'b.py'])
  })

  it('drops files inside .git, node_modules, __pycache__ and .DS_Store files', () => {
    const entries = toFolderEntries([
      makeFile('main.py', 'x', 'app/main.py'),
      makeFile('config', 'x', 'app/.git/config'),
      makeFile('index.js', 'x', 'app/node_modules/a/index.js'),
      makeFile('m.pyc', 'x', 'app/__pycache__/m.pyc'),
      makeFile('.DS_Store', 'x', 'app/.DS_Store'),
    ])
    const { kept, excludedPaths } = splitExcluded(entries)
    expect(kept.map((e) => e.path)).toEqual(['app/main.py'])
    expect(excludedPaths).toEqual([
      'app/.git/config',
      'app/node_modules/a/index.js',
      'app/__pycache__/m.pyc',
      'app/.DS_Store',
    ])
  })

  it('does not exclude a file merely named like an excluded directory', () => {
    const { kept } = splitExcluded(
      toFolderEntries([makeFile('node_modules', 'x', 'app/node_modules')]),
    )
    expect(kept).toHaveLength(1)
  })

  it('has the contract notice text', () => {
    expect(EXCLUDED_NOTICE).toBe(
      '일반적인 빌드/시스템 폴더를 제외했습니다: .git, node_modules, __pycache__',
    )
  })
})

describe('validatePaste', () => {
  it('requires a language before anything else', () => {
    expect(validatePaste('print(1)', '')).toBe('업로드하기 전에 프로그래밍 언어를 선택하세요.')
  })

  it('rejects empty or whitespace-only code', () => {
    expect(validatePaste('  \n ', 'python')).toBe('붙여넣은 코드가 비어 있습니다.')
  })

  it('accepts code with a language', () => {
    expect(validatePaste('print(1)', 'python')).toBeUndefined()
  })

  it('rejects code over 10MB', () => {
    expect(validatePaste('a'.repeat(MAX_TOTAL_BYTES + 1), 'python')).toBe(
      '업로드한 파일의 전체 크기가 10MB를 초과합니다.',
    )
  })
})
