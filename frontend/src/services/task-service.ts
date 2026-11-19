import { apiClient } from './api-client'

// Thin typed wrappers over the task endpoints. The shapes follow
// specs/001-ai-code-learning-platform/contracts/phase5-tasks-upload-api.md.

export type UploadMethod = 'file' | 'folder' | 'paste'
export type ComplexityLevel = 'beginner' | 'intermediate' | 'advanced'

export interface TaskUpload {
  detected_language: string | null
  complexity_level: ComplexityLevel | null
  total_lines: number
  total_files: number
  upload_size_bytes: number
}

export interface Task {
  id: string
  project_id: string
  task_number: number
  title: string
  description: string | null
  upload_method: UploadMethod | null
  created_at: string
  updated_at: string
  upload: TaskUpload | null
}

export interface CodeFileSummary {
  id: string
  file_name: string
  file_path: string | null
  file_extension: string | null
  file_size_bytes: number
  mime_type: string | null
}

export interface TaskDetail extends Task {
  files: CodeFileSummary[]
}

export interface UploadWarning {
  code: string
  message: string
}

export interface CreateTaskResult extends TaskDetail {
  excluded_paths: string[]
  warnings: UploadWarning[]
}

export interface TaskCodeFile extends CodeFileSummary {
  language: string
  content: string
}

export interface TaskCode {
  files: TaskCodeFile[]
}

// A folder pick: the file plus its "/"-separated path relative to the chosen folder.
export interface FolderEntry {
  file: File
  path: string
}

export type TaskUploadInput =
  | { method: 'file'; files: File[] }
  | { method: 'folder'; entries: FolderEntry[] }
  | { method: 'paste'; code: string; language: string }

export interface CreateTaskInput {
  title: string
  description?: string
  upload: TaskUploadInput
}

// Partial update: only the keys present are sent; an explicit null description clears it.
export interface UpdateTaskInput {
  title?: string
  description?: string | null
}

export async function listTasks(projectId: string): Promise<Task[]> {
  const { data } = await apiClient.get<Task[]>(`/projects/${projectId}/tasks`)
  return data
}

// Multipart body. Content-Type is left to axios so it adds the boundary itself.
function toFormData({ title, description, upload }: CreateTaskInput): FormData {
  const form = new FormData()
  form.append('title', title)
  if (description) form.append('description', description)
  form.append('upload_method', upload.method)
  if (upload.method === 'file') {
    upload.files.forEach((file) => form.append('files', file))
  } else if (upload.method === 'folder') {
    // files and paths are repeated parts that the server pairs up by order.
    upload.entries.forEach(({ file, path }) => {
      form.append('files', file)
      form.append('paths', path)
    })
  } else {
    form.append('code', upload.code)
    form.append('language', upload.language)
  }
  return form
}

export async function createTask(
  projectId: string,
  input: CreateTaskInput,
): Promise<CreateTaskResult> {
  const { data } = await apiClient.post<CreateTaskResult>(
    `/projects/${projectId}/tasks`,
    toFormData(input),
  )
  return data
}

export async function getTask(id: string): Promise<TaskDetail> {
  const { data } = await apiClient.get<TaskDetail>(`/tasks/${id}`)
  return data
}

export async function updateTask(id: string, input: UpdateTaskInput): Promise<Task> {
  const { data } = await apiClient.patch<Task>(`/tasks/${id}`, input)
  return data
}

export async function deleteTask(id: string): Promise<void> {
  await apiClient.delete(`/tasks/${id}`)
}

export async function getTaskCode(id: string): Promise<TaskCode> {
  const { data } = await apiClient.get<TaskCode>(`/tasks/${id}/code`)
  return data
}
