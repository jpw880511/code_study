import { apiClient, isApiError } from './api-client'

// Typed wrappers over the document endpoints. The shapes follow
// specs/001-ai-code-learning-platform/contracts/phase6-document-generation-api.md.

export type DocumentStatus = 'pending' | 'in_progress' | 'completed' | 'failed'

export interface DocumentStatusInfo {
  status: DocumentStatus
  generation_started_at: string | null
  generation_completed_at: string | null
  // Computed by the server at response time, so browser clock drift does not matter.
  elapsed_seconds: number | null
  estimated_total_seconds: number | null
  notice: string | null
  error: string | null
}

export interface Chapter1 {
  title: string
  summary: string
}

export interface Chapter2Concept {
  name: string
  explanation: string
  analogy: string
  example: string
  use_cases: string // one text, not a list (see the structure in the Phase 6 contract)
}

export interface Chapter2 {
  title: string
  concepts: Chapter2Concept[]
}

export interface Chapter3 {
  title: string
  flowchart: string
  file_breakdown: Record<string, string>
}

export interface LineExplanation {
  file: string
  line_start: number
  line_end: number
  code: string
  what_it_does: string
  syntax_breakdown: string
  analogy: string
  alternatives: string
  notes: string
}

export interface Chapter4 {
  title: string
  explanations: LineExplanation[]
}

export interface FlowStep {
  step: number
  description: string
  data: string
}

export interface Chapter5 {
  title: string
  steps: FlowStep[]
}

export interface KeyConcept {
  name: string
  what_it_is: string
  why_its_used: string
  where_its_applied: string
}

export interface Chapter6 {
  title: string
  concepts: KeyConcept[]
}

export interface CommonMistake {
  wrong: string
  right: string
  why: string
  fix: string
}

export interface Chapter7 {
  title: string
  mistakes: CommonMistake[]
}

export interface DocumentContent {
  chapter1: Chapter1
  chapter2: Chapter2
  chapter3: Chapter3
  chapter4: Chapter4
  chapter5: Chapter5
  chapter6: Chapter6
  chapter7: Chapter7
}

export interface TaskDocument {
  task_id: string
  status: DocumentStatus
  // Only present once the document is completed.
  content: DocumentContent | null
  generation_started_at: string | null
  generation_completed_at: string | null
  error: string | null
  created_at: string
  updated_at: string
}

// A task that never got a document answers 404 document_not_found. That is a state, not a
// failure, so it becomes null; every other error (task_not_found, 403, network) still throws.
async function orNullWhenMissing<T>(request: Promise<{ data: T }>): Promise<T | null> {
  try {
    return (await request).data
  } catch (error) {
    if (isApiError(error) && error.code === 'document_not_found') return null
    throw error
  }
}

export function getDocumentStatus(taskId: string): Promise<DocumentStatusInfo | null> {
  return orNullWhenMissing(apiClient.get<DocumentStatusInfo>(`/tasks/${taskId}/document/status`))
}

export function getDocument(taskId: string): Promise<TaskDocument | null> {
  return orNullWhenMissing(apiClient.get<TaskDocument>(`/tasks/${taskId}/document`))
}
