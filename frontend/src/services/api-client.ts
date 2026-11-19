import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

export const DEFAULT_API_BASE_URL = 'http://localhost:8000/api/v1'
export const REQUEST_TIMEOUT_MS = 30_000

const MESSAGES = {
  http_error: '요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요.',
  network_error: '서버에 연결할 수 없습니다. 네트워크 상태를 확인하세요.',
  timeout: '서버 응답이 지연되고 있습니다. 잠시 후 다시 시도하세요.',
}

// Mirrors the backend's ErrorResponse (backend/src/api/exceptions.py).
interface ErrorBody {
  error?: unknown
  message?: unknown
  details?: Record<string, unknown>
  suggestion?: unknown
}

export class ApiError extends Error {
  status?: number
  code: string
  details?: Record<string, unknown>
  suggestion?: string
  // The request that failed, so callers (e.g. the session refresh) can replay it.
  config?: InternalAxiosRequestConfig

  constructor(init: {
    message: string
    code: string
    status?: number
    details?: Record<string, unknown>
    suggestion?: string
    config?: InternalAxiosRequestConfig
  }) {
    super(init.message)
    this.name = 'ApiError'
    this.code = init.code
    this.status = init.status
    this.details = init.details
    this.suggestion = init.suggestion
    this.config = init.config
  }
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value !== '' ? value : undefined
}

function toApiError(error: AxiosError): ApiError {
  const { response } = error
  if (response) {
    const body: ErrorBody = typeof response.data === 'object' && response.data ? response.data : {}
    return new ApiError({
      status: response.status,
      code: text(body.error) ?? 'http_error',
      message: text(body.message) ?? MESSAGES.http_error,
      details: body.details,
      suggestion: text(body.suggestion),
      config: error.config,
    })
  }
  const timedOut = error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT'
  const code = timedOut ? 'timeout' : 'network_error'
  return new ApiError({ code, message: MESSAGES[code], config: error.config })
}

export const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL ?? DEFAULT_API_BASE_URL,
  withCredentials: true, // the JWT lives in HTTP-only cookies
  timeout: REQUEST_TIMEOUT_MS,
  headers: { Accept: 'application/json' },
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    // Cancelled requests must stay as they are so TanStack Query can handle them.
    if (axios.isAxiosError(error) && !axios.isCancel(error)) {
      return Promise.reject(toApiError(error))
    }
    return Promise.reject(error)
  },
)
