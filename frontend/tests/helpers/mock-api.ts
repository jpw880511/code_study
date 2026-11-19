import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { afterEach, beforeEach, vi } from 'vitest'

import { apiClient } from '../../src/services/api-client'

// A mocked axios adapter for the shared apiClient: every request goes through the real
// interceptors (so errors become ApiError) but never reaches the network.

export type MockHandler = (config: InternalAxiosRequestConfig) => Promise<unknown> | unknown

export function reply(config: InternalAxiosRequestConfig, status: number, data?: unknown) {
  const response = { data, status, statusText: '', headers: {}, config, request: {} }
  if (status < 400) return Promise.resolve(response)
  return Promise.reject(new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, {}, response))
}

export function networkFailure(config: InternalAxiosRequestConfig) {
  return Promise.reject(new AxiosError('Network Error', 'ERR_NETWORK', config))
}

export function errorBody(error: string, message = '오류가 발생했습니다.') {
  return { error, message }
}

export function route(method: string, url: string) {
  return `${method.toUpperCase()} ${url}`
}

export function requestKey(config: InternalAxiosRequestConfig) {
  return route(config.method ?? 'get', config.url ?? '')
}

// Installs the adapter mock around each test and returns it for per-test behaviour.
export function mockApi() {
  const adapter = vi.fn<(config: InternalAxiosRequestConfig) => Promise<unknown>>()
  const original = apiClient.defaults.adapter
  beforeEach(() => {
    adapter.mockReset()
    apiClient.defaults.adapter = adapter as never
  })
  afterEach(() => {
    apiClient.defaults.adapter = original
  })
  return adapter
}

// Convenience: answer by "METHOD /url" key; unknown requests fail the test loudly.
export function respondByRoute(
  adapter: ReturnType<typeof mockApi>,
  handlers: Record<string, MockHandler>,
) {
  adapter.mockImplementation(async (config) => {
    const handler = handlers[requestKey(config)]
    if (!handler) throw new Error(`Unexpected request: ${requestKey(config)}`)
    return handler(config)
  })
}
