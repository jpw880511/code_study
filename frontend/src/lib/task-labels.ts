import type { ComplexityLevel } from '../services/task-service'

const COMPLEXITY_LABELS: Record<ComplexityLevel, string> = {
  beginner: '초급',
  intermediate: '중급',
  advanced: '고급',
}

export function complexityLabel(level: ComplexityLevel): string {
  return COMPLEXITY_LABELS[level]
}

// "1.5 KB" style size for the file lists.
export function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
