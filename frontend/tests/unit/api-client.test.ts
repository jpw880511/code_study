import axios, { AxiosError, type AxiosAdapter, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { shouldRetry } from '../../src/lib/queryClient'
import {
  ApiError,
  DEFAULT_API_BASE_URL,
  apiClient,
  isApiError,
} from '../../src/services/api-client'

const originalAdapter = apiClient.defaults.adapter

function stubResponse(status: number, data: unknown) {
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    const response = { data, status, statusText: '', headers: {}, config, request: {} }
    if (status >= 200 && status < 300) return response
    throw new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, {}, response)
  }
}

function stubFailure(code: string, message: string) {
  apiClient.defaults.adapter = async (config: InternalAxiosRequestConfig) => {
    throw new AxiosError(message, code, config)
  }
}

function captureRequests() {
  const seen: InternalAxiosRequestConfig[] = []
  const adapter: AxiosAdapter = async (config) => {
    seen.push(config)
    return { data: {}, status: 200, statusText: 'OK', headers: {}, config, request: {} }
  }
  apiClient.defaults.adapter = adapter
  return seen
}

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
  vi.unstubAllEnvs()
  vi.resetModules()
})

describe('configuration', () => {
  it('targets the local /api/v1 backend by default', () => {
    expect(DEFAULT_API_BASE_URL).toBe('http://localhost:8000/api/v1')
    expect(apiClient.defaults.baseURL).toBe(DEFAULT_API_BASE_URL)
  })

  it('sends cookies so the HTTP-only JWT cookies work cross-origin', () => {
    expect(apiClient.defaults.withCredentials).toBe(true)
  })

  it('times out after 30 seconds and asks for JSON', () => {
    expect(apiClient.defaults.timeout).toBe(30_000)
    expect(apiClient.defaults.headers.Accept).toBe('application/json')
  })

  it('reads the base URL from VITE_API_BASE_URL', async () => {
    vi.stubEnv('VITE_API_BASE_URL', 'https://api.example.com/api/v1')
    vi.resetModules()
    const module = await import('../../src/services/api-client')
    expect(module.apiClient.defaults.baseURL).toBe('https://api.example.com/api/v1')
  })

  it('resolves request paths against the base URL', async () => {
    const seen = captureRequests()
    await apiClient.get('/health')
    expect(seen[0].baseURL).toBe(DEFAULT_API_BASE_URL)
    expect(seen[0].url).toBe('/health')
  })
})

describe('successful responses', () => {
  it('passes the response data through untouched', async () => {
    stubResponse(200, { status: 'ok' })
    const response = await apiClient.get('/health')
    expect(response.status).toBe(200)
    expect(response.data).toEqual({ status: 'ok' })
  })

  it('serializes request bodies as JSON', async () => {
    const seen = captureRequests()
    await apiClient.post('/projects', { title: '새 프로젝트' })
    expect(seen[0].headers['Content-Type']).toContain('application/json')
    expect(seen[0].data).toBe(JSON.stringify({ title: '새 프로젝트' }))
  })
})

describe('error normalization', () => {
  it('turns the backend error body into an ApiError', async () => {
    stubResponse(404, { error: 'not_found', message: '요청한 항목을 찾을 수 없습니다.' })
    const error = await apiClient.get('/projects/1').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toBeInstanceOf(Error)
    expect(isApiError(error)).toBe(true)
    const apiError = error as ApiError
    expect(apiError.name).toBe('ApiError')
    expect(apiError.status).toBe(404)
    expect(apiError.code).toBe('not_found')
    expect(apiError.message).toBe('요청한 항목을 찾을 수 없습니다.')
    expect(apiError.details).toBeUndefined()
    expect(apiError.suggestion).toBeUndefined()
  })

  it('keeps details and suggestion from the backend', async () => {
    stubResponse(409, {
      error: 'conflict',
      message: '요청이 현재 상태와 충돌합니다.',
      details: { project_id: 'p1' },
      suggestion: '새로고침 후 다시 시도하세요.',
    })
    const error = (await apiClient.patch('/projects/p1', {}).catch((e: unknown) => e)) as ApiError
    expect(error.status).toBe(409)
    expect(error.details).toEqual({ project_id: 'p1' })
    expect(error.suggestion).toBe('새로고침 후 다시 시도하세요.')
  })

  it('keeps the field list of a validation error', async () => {
    const errors = [{ field: 'body.title', message: 'Field required', type: 'missing' }]
    stubResponse(422, {
      error: 'validation_error',
      message: '입력값이 올바르지 않습니다.',
      details: { errors },
    })
    const error = (await apiClient.post('/projects', {}).catch((e: unknown) => e)) as ApiError
    expect(error.code).toBe('validation_error')
    expect(error.details).toEqual({ errors })
  })

  it.each([
    ['an HTML error page', '<html>Bad Gateway</html>'],
    ['an empty body', ''],
    ['a JSON body without the expected fields', { oops: true }],
    ['a null body', null],
  ])('falls back to a generic error for %s', async (_label, body) => {
    stubResponse(502, body)
    const error = (await apiClient.get('/health').catch((e: unknown) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(502)
    expect(error.code).toBe('http_error')
    expect(error.message).toBe('요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요.')
  })

  it('ignores non-string error fields in the body', async () => {
    stubResponse(500, { error: 42, message: { nested: true } })
    const error = (await apiClient.get('/health').catch((e: unknown) => e)) as ApiError
    expect(error.code).toBe('http_error')
    expect(error.message).toBe('요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요.')
  })

  it('reports an unreachable server as network_error without a status', async () => {
    stubFailure('ERR_NETWORK', 'Network Error')
    const error = (await apiClient.get('/health').catch((e: unknown) => e)) as ApiError
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBeUndefined()
    expect(error.code).toBe('network_error')
    expect(error.message).toBe('서버에 연결할 수 없습니다. 네트워크 상태를 확인하세요.')
  })

  it.each(['ECONNABORTED', 'ETIMEDOUT'])('reports %s as a timeout', async (code) => {
    stubFailure(code, 'timeout of 30000ms exceeded')
    const error = (await apiClient.get('/health').catch((e: unknown) => e)) as ApiError
    expect(error.code).toBe('timeout')
    expect(error.status).toBeUndefined()
    expect(error.message).toBe('서버 응답이 지연되고 있습니다. 잠시 후 다시 시도하세요.')
  })

  it('leaves cancelled requests alone so TanStack Query can cancel them', async () => {
    apiClient.defaults.adapter = async () => {
      throw new axios.CanceledError('canceled')
    }
    const error = await apiClient.get('/health').catch((e: unknown) => e)
    expect(axios.isCancel(error)).toBe(true)
    expect(error).not.toBeInstanceOf(ApiError)
  })

  it('does not wrap errors that are not HTTP errors', async () => {
    apiClient.defaults.adapter = async () => {
      throw new TypeError('boom')
    }
    const error = await apiClient.get('/health').catch((e: unknown) => e)
    expect(error).toBeInstanceOf(TypeError)
  })
})

describe('isApiError', () => {
  it('is false for other values', () => {
    expect(isApiError(new Error('x'))).toBe(false)
    expect(isApiError(null)).toBe(false)
    expect(isApiError({ status: 404 })).toBe(false)
  })
})

describe('integration with the query client retry rules', () => {
  async function failWith(status: number): Promise<unknown> {
    stubResponse(status, { error: 'x', message: 'y' })
    return apiClient.get('/health').catch((e: unknown) => e)
  }

  it('does not retry a 404 ApiError', async () => {
    expect(shouldRetry(0, await failWith(404))).toBe(false)
  })

  it('retries a 500 ApiError', async () => {
    expect(shouldRetry(0, await failWith(500))).toBe(true)
  })

  it('retries a network ApiError', async () => {
    stubFailure('ERR_NETWORK', 'Network Error')
    const error = await apiClient.get('/health').catch((e: unknown) => e)
    expect(shouldRetry(0, error)).toBe(true)
    expect(shouldRetry(2, error)).toBe(false)
  })
})
