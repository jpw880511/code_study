import type {
  CodeFileSummary,
  CreateTaskResult,
  Task,
  TaskDetail,
} from '../../src/services/task-service'

export function makeTask(overrides: Partial<Task> = {}): Task {
  return {
    id: 't-1',
    project_id: 'p-1',
    task_number: 1,
    title: '계산기 함수 학습',
    description: '덧셈과 뺄셈을 배웁니다.',
    upload_method: 'file',
    created_at: '2026-11-16T09:00:00Z',
    updated_at: '2026-11-16T09:00:00Z',
    upload: {
      detected_language: 'python',
      complexity_level: 'beginner',
      total_lines: 120,
      total_files: 1,
      upload_size_bytes: 4096,
    },
    ...overrides,
  }
}

export function makeCodeFile(overrides: Partial<CodeFileSummary> = {}): CodeFileSummary {
  return {
    id: 'f-1',
    file_name: 'calc.py',
    file_path: null,
    file_extension: '.py',
    file_size_bytes: 2048,
    mime_type: 'text/x-python',
    ...overrides,
  }
}

export function makeTaskDetail(overrides: Partial<TaskDetail> = {}): TaskDetail {
  return { ...makeTask(), files: [makeCodeFile()], ...overrides }
}

export function makeCreateResult(overrides: Partial<CreateTaskResult> = {}): CreateTaskResult {
  return { ...makeTaskDetail(), excluded_paths: [], warnings: [], ...overrides }
}

// A browser File; webkitRelativePath is read-only, so it is defined on the instance.
export function makeFile(name: string, content = 'print(1)\n', relativePath?: string): File {
  const file = new File([content], name, { type: 'text/plain' })
  if (relativePath !== undefined) {
    Object.defineProperty(file, 'webkitRelativePath', { value: relativePath })
  }
  return file
}

// A File that reports the given byte size without allocating that much memory.
export function makeSizedFile(name: string, size: number): File {
  const file = makeFile(name)
  Object.defineProperty(file, 'size', { value: size })
  return file
}
