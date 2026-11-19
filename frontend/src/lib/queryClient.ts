import { QueryClient } from '@tanstack/react-query'

const MAX_RETRIES = 2
const STALE_TIME_MS = 60_000
const MAX_RETRY_DELAY_MS = 10_000

// Works with axios errors (error.response.status) and plain { status } errors.
export function getErrorStatus(error: unknown): number | undefined {
  if (typeof error !== 'object' || error === null) return undefined
  const { response, status } = error as { response?: { status?: unknown }; status?: unknown }
  if (typeof response?.status === 'number') return response.status
  return typeof status === 'number' ? status : undefined
}

// A 4xx answer will not change on a retry; network failures and 5xx might.
export function shouldRetry(failureCount: number, error: unknown): boolean {
  const status = getErrorStatus(error)
  if (status !== undefined && status >= 400 && status < 500) return false
  return failureCount < MAX_RETRIES
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: STALE_TIME_MS,
        refetchOnWindowFocus: false,
        retry: shouldRetry,
        retryDelay: (attempt) => Math.min(1000 * 2 ** attempt, MAX_RETRY_DELAY_MS),
      },
      mutations: { retry: false },
    },
  })
}

export const queryClient = createQueryClient()
