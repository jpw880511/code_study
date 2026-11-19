import type { FolderEntry } from '../services/task-service'

// Client-side checks for fast feedback only; the server stays the authority. They mirror
// the rules in specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md.

export const MIN_TITLE_LENGTH = 5
export const MAX_TITLE_LENGTH = 255
export const MAX_DESCRIPTION_LENGTH = 500

export const SUPPORTED_EXTENSIONS = [
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
]

export const MAX_TOTAL_BYTES = 10 * 1024 * 1024
export const MIN_FILES = 1
export const MAX_FILES = 20

export const EXCLUDED_DIRECTORIES = ['.git', 'node_modules', '__pycache__']
export const EXCLUDED_FILES = ['.DS_Store']
export const EXCLUDED_NOTICE =
  '일반적인 빌드/시스템 폴더를 제외했습니다: .git, node_modules, __pycache__'

// The dropdown value goes to the server; the label is what the user reads.
export const PASTE_LANGUAGES = [
  { value: 'python', label: 'Python' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'typescript', label: 'TypeScript' },
  { value: 'java', label: 'Java' },
  { value: 'c', label: 'C' },
  { value: 'cpp', label: 'C++' },
  { value: 'html', label: 'HTML' },
  { value: 'css', label: 'CSS' },
  { value: 'markdown', label: 'Markdown' },
  { value: 'text', label: '텍스트' },
]

const TOTAL_TOO_LARGE = '업로드한 파일의 전체 크기가 10MB를 초과합니다.'

export function validateTaskTitle(title: string): string | undefined {
  const length = title.trim().length
  if (length < MIN_TITLE_LENGTH) return 'Task 제목은 최소 5자 이상이어야 합니다.'
  if (length > MAX_TITLE_LENGTH) return 'Task 제목은 최대 255자까지 입력 가능합니다.'
}

export function validateTaskDescription(description: string): string | undefined {
  if (description.trim().length > MAX_DESCRIPTION_LENGTH) {
    return 'Task 설명은 최대 500자까지 입력 가능합니다.'
  }
}

function extensionOf(fileName: string): string {
  const dot = fileName.lastIndexOf('.')
  return dot > 0 ? fileName.slice(dot).toLowerCase() : ''
}

// Same order as the server: count, then each file (extension, size), then the total.
export function validateUploadFiles(files: Pick<File, 'name' | 'size'>[]): string | undefined {
  if (files.length < MIN_FILES) return '업로드할 파일을 선택하세요.'
  if (files.length > MAX_FILES) {
    return '업로드당 최대 20개 파일까지 가능합니다. 파일 수를 줄이거나 폴더 업로드를 사용하세요.'
  }
  for (const file of files) {
    const extension = extensionOf(file.name)
    if (!SUPPORTED_EXTENSIONS.includes(extension)) {
      return `지원하지 않는 파일 형식입니다 (${extension || '확장자 없음'}). 지원 형식: ${SUPPORTED_EXTENSIONS.join(', ')}`
    }
    if (file.size > MAX_TOTAL_BYTES) return '파일 크기가 10MB를 초과합니다.'
  }
  const total = files.reduce((sum, file) => sum + file.size, 0)
  if (total > MAX_TOTAL_BYTES) return TOTAL_TOO_LARGE
}

export function validatePaste(code: string, language: string): string | undefined {
  if (!language) return '업로드하기 전에 프로그래밍 언어를 선택하세요.'
  if (code.trim() === '') return '붙여넣은 코드가 비어 있습니다.'
  if (new Blob([code]).size > MAX_TOTAL_BYTES) return TOTAL_TOO_LARGE
}

// Folder picks carry webkitRelativePath ("my-app/src/App.jsx"); a plain file has none.
export function toFolderEntries(files: ArrayLike<File>): FolderEntry[] {
  return Array.from(files, (file) => ({ file, path: file.webkitRelativePath || file.name }))
}

function isExcluded(path: string): boolean {
  const segments = path.split('/')
  const fileName = segments.pop() ?? ''
  return EXCLUDED_FILES.includes(fileName) || segments.some((s) => EXCLUDED_DIRECTORIES.includes(s))
}

export function splitExcluded(entries: FolderEntry[]): {
  kept: FolderEntry[]
  excludedPaths: string[]
} {
  const kept = entries.filter((entry) => !isExcluded(entry.path))
  const excludedPaths = entries.filter((entry) => isExcluded(entry.path)).map((e) => e.path)
  return { kept, excludedPaths }
}
