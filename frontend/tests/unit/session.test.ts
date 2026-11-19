import { beforeEach, describe, expect, it } from 'vitest'

import { apiClient } from '../../src/services/api-client'
import { installSessionRefresh, refreshSession } from '../../src/services/session'
import { useAuthStore } from '../../src/stores/auth-store'
import { errorBody, reply, requestKey, respondByRoute, mockApi } from '../helpers/mock-api'

const adapter = mockApi()
const alice = { id: 'u-1', email: 'a@example.com', skill_level: null }

function calls(key: string) {
  return adapter.mock.calls.filter(([config]) => requestKey(config) === key).length
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  useAuthStore.getState().setUser(alice)
})

describe('refreshSession (single flight)', () => {
  it('shares one POST /auth/refresh between concurrent callers', async () => {
    let finish: () => void = () => {}
    adapter.mockImplementation(
      (config) => new Promise((resolve) => (finish = () => resolve(reply(config, 204)))),
    )
    const first = refreshSession()
    const second = refreshSession()
    await Promise.resolve()
    finish()
    await Promise.all([first, second])
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('starts a new refresh once the previous one has finished', async () => {
    adapter.mockImplementation((config) => reply(config, 204))
    await refreshSession()
    await refreshSession()
    expect(adapter).toHaveBeenCalledTimes(2)
  })

  it('allows a new refresh after a failed one', async () => {
    adapter.mockImplementationOnce((config) => reply(config, 401, errorBody('session_expired')))
    await expect(refreshSession()).rejects.toMatchObject({ code: 'session_expired' })
    adapter.mockImplementation((config) => reply(config, 204))
    await expect(refreshSession()).resolves.toBeUndefined()
  })
})

describe('installSessionRefresh (reactive refresh)', () => {
  let eject: () => void
  beforeEach(() => {
    eject = installSessionRefresh()
    return () => eject()
  })

  it('refreshes once and retries the original request once on 401 session_expired', async () => {
    let projectAttempts = 0
    respondByRoute(adapter, {
      'GET /projects': (config) =>
        ++projectAttempts === 1
          ? reply(config, 401, errorBody('session_expired'))
          : reply(config, 200, [{ id: 'p1' }]),
      'POST /auth/refresh': (config) => reply(config, 204),
    })
    const response = await apiClient.get('/projects')
    expect(response.data).toEqual([{ id: 'p1' }])
    expect(calls('GET /projects')).toBe(2)
    expect(calls('POST /auth/refresh')).toBe(1)
    expect(useAuthStore.getState().status).toBe('authenticated')
  })

  it('retries a POST with its original body', async () => {
    let attempts = 0
    respondByRoute(adapter, {
      'POST /projects': (config) =>
        ++attempts === 1
          ? reply(config, 401, errorBody('session_expired'))
          : reply(config, 201, {}),
      'POST /auth/refresh': (config) => reply(config, 204),
    })
    await apiClient.post('/projects', { name: 'demo' })
    const retry = adapter.mock.calls.filter(([c]) => requestKey(c) === 'POST /projects')[1][0]
    expect(JSON.parse(retry.data)).toEqual({ name: 'demo' })
  })

  it('shares one refresh between concurrent 401s and retries each request', async () => {
    const attempts: Record<string, number> = {}
    const handlerFor = (config: Parameters<typeof reply>[0]) =>
      (attempts[config.url!] = (attempts[config.url!] ?? 0) + 1) === 1
        ? reply(config, 401, errorBody('session_expired'))
        : reply(config, 200, config.url)
    respondByRoute(adapter, {
      'GET /a': handlerFor,
      'GET /b': handlerFor,
      'GET /c': handlerFor,
      'POST /auth/refresh': (config) => reply(config, 204),
    })
    const results = await Promise.all(['/a', '/b', '/c'].map((url) => apiClient.get(url)))
    expect(results.map((r) => r.data)).toEqual(['/a', '/b', '/c'])
    expect(calls('POST /auth/refresh')).toBe(1)
  })

  it('retries only once: a second session_expired is surfaced, not looped', async () => {
    respondByRoute(adapter, {
      'GET /projects': (config) => reply(config, 401, errorBody('session_expired', '만료')),
      'POST /auth/refresh': (config) => reply(config, 204),
    })
    await expect(apiClient.get('/projects')).rejects.toMatchObject({ code: 'session_expired' })
    expect(calls('GET /projects')).toBe(2)
    expect(calls('POST /auth/refresh')).toBe(1)
  })

  it('clears the store and surfaces the original error when the refresh fails', async () => {
    respondByRoute(adapter, {
      'GET /projects': (config) => reply(config, 401, errorBody('session_expired', '원래 오류')),
      'POST /auth/refresh': (config) => reply(config, 401, errorBody('not_authenticated')),
    })
    await expect(apiClient.get('/projects')).rejects.toMatchObject({
      code: 'session_expired',
      message: '원래 오류',
    })
    expect(calls('GET /projects')).toBe(1)
    expect(useAuthStore.getState().status).toBe('unauthenticated')
  })

  it.each([
    ['/auth/me', 'get'],
    ['/auth/refresh', 'post'],
    ['/auth/login', 'post'],
  ])('never refreshes because of a failing %s', async (url, method) => {
    adapter.mockImplementation((config) => reply(config, 401, errorBody('session_expired')))
    await expect(apiClient.request({ url, method })).rejects.toMatchObject({
      code: 'session_expired',
    })
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it.each([
    [401, 'not_authenticated'],
    [403, 'session_expired'],
    [500, 'internal_error'],
  ])('ignores %s %s', async (status, code) => {
    adapter.mockImplementation((config) => reply(config, status, errorBody(code)))
    await expect(apiClient.get('/projects')).rejects.toMatchObject({ code })
    expect(adapter).toHaveBeenCalledTimes(1)
  })

  it('passes non-API errors through untouched', async () => {
    const failure = new Error('boom')
    adapter.mockRejectedValue(failure)
    await expect(apiClient.get('/projects')).rejects.toBe(failure)
  })

  it('stops refreshing once ejected', async () => {
    eject()
    adapter.mockImplementation((config) => reply(config, 401, errorBody('session_expired')))
    await expect(apiClient.get('/projects')).rejects.toMatchObject({ code: 'session_expired' })
    expect(adapter).toHaveBeenCalledTimes(1)
  })
})
