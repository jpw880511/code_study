import { useQuery } from '@tanstack/react-query'

import { getDocument, getDocumentStatus, type DocumentStatus } from '../services/document-service'
import { getTaskCode } from '../services/task-service'

export const STATUS_POLL_INTERVAL_MS = 2000

const statusKey = (taskId: string) => ['tasks', taskId, 'document', 'status'] as const
const documentKey = (taskId: string) => ['tasks', taskId, 'document'] as const
const codeKey = (taskId: string) => ['tasks', taskId, 'code'] as const

function isWorking(status: DocumentStatus | undefined): boolean {
  return status === 'pending' || status === 'in_progress'
}

// Polls only while the worker has not finished; completed, failed and "no document" (null) stop it.
// TanStack Query also stops the interval when the last observer unmounts.
export function useDocumentStatus(taskId: string) {
  return useQuery({
    queryKey: statusKey(taskId),
    queryFn: () => getDocumentStatus(taskId),
    refetchInterval: (query) =>
      isWorking(query.state.data?.status) ? STATUS_POLL_INTERVAL_MS : false,
    // The status changes by itself, so a cached answer must not be reused as fresh.
    staleTime: 0,
  })
}

// The document never changes once completed, so it is fetched once.
export function useTaskDocument(taskId: string, enabled: boolean) {
  return useQuery({
    queryKey: documentKey(taskId),
    queryFn: () => getDocument(taskId),
    enabled,
    staleTime: Infinity,
  })
}

export function useTaskCode(taskId: string, enabled: boolean) {
  return useQuery({
    queryKey: codeKey(taskId),
    queryFn: () => getTaskCode(taskId),
    enabled,
  })
}
