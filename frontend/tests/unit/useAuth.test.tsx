import { act, renderHook, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { REFRESH_INTERVAL_MS, useAuth, useAuthBootstrap } from '../../src/hooks/useAuth'
import { apiClient } from '../../src/services/api-client'
import { useAuthStore } from '../../src/stores/auth-store'
import {
  errorBody,
  networkFailure,
  reply,
  requestKey,
  respondByRoute,
  mockApi,
} from '../helpers/mock-api'

const adapter = mockApi()
const alice = { id: 'u-1', email: 'a@example.com', skill_level: null }

function count(key: string) {
  return adapter.mock.calls.filter(([config]) => requestKey(config) === key).length
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

afterEach(() => {
  vi.useRealTimers()
})

describe('useAuthBootstrap: start-up', () => {
  it('stores the user when GET /auth/me succeeds', async () => {
    respondByRoute(adapter, { 'GET /auth/me': (c) => reply(c, 200, alice) })
    renderHook(() => useAuthBootstrap())
    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'))
    expect(useAuthStore.getState().user).toEqual(alice)
    expect(count('GET /auth/me')).toBe(1)
  })

  it('refreshes once and asks again when the access token expired', async () => {
    let meCalls = 0
    respondByRoute(adapter, {
      'GET /auth/me': (c) =>
        ++meCalls === 1 ? reply(c, 401, errorBody('session_expired')) : reply(c, 200, alice),
      'POST /auth/refresh': (c) => reply(c, 204),
    })
    renderHook(() => useAuthBootstrap())
    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'))
    expect(count('POST /auth/refresh')).toBe(1)
    expect(count('GET /auth/me')).toBe(2)
  })

  it('becomes unauthenticated when the refresh fails', async () => {
    respondByRoute(adapter, {
      'GET /auth/me': (c) => reply(c, 401, errorBody('session_expired')),
      'POST /auth/refresh': (c) => reply(c, 401, errorBody('session_expired')),
    })
    renderHook(() => useAuthBootstrap())
    await waitFor(() => expect(useAuthStore.getState().status).toBe('unauthenticated'))
    expect(count('GET /auth/me')).toBe(1)
  })

  it('becomes unauthenticated when /auth/me still fails after the refresh', async () => {
    respondByRoute(adapter, {
      'GET /auth/me': (c) => reply(c, 401, errorBody('session_expired')),
      'POST /auth/refresh': (c) => reply(c, 204),
    })
    renderHook(() => useAuthBootstrap())
    await waitFor(() => expect(useAuthStore.getState().status).toBe('unauthenticated'))
    expect(count('POST /auth/refresh')).toBe(1)
  })

  it('does not refresh for a plain 401 not_authenticated', async () => {
    respondByRoute(adapter, {
      'GET /auth/me': (c) => reply(c, 401, errorBody('not_authenticated')),
    })
    renderHook(() => useAuthBootstrap())
    await waitFor(() => expect(useAuthStore.getState().status).toBe('unauthenticated'))
    expect(count('POST /auth/refresh')).toBe(0)
  })

  it.each([
    ['a network error', networkFailure],
    ['a server error', (c: Parameters<typeof reply>[0]) => reply(c, 500, errorBody('internal'))],
  ])('does not stay on unknown after %s', async (_name, fail) => {
    respondByRoute(adapter, { 'GET /auth/me': fail })
    renderHook(() => useAuthBootstrap())
    await waitFor(() => expect(useAuthStore.getState().status).toBe('unauthenticated'))
  })

  it.each(['authenticated', 'unauthenticated'] as const)(
    'does not ask the server when the status is already %s',
    async (status) => {
      if (status === 'authenticated') useAuthStore.getState().setUser(alice)
      else useAuthStore.getState().clearUser()
      renderHook(() => useAuthBootstrap())
      await act(async () => {})
      expect(adapter).not.toHaveBeenCalled()
    },
  )

  it('asks only once even when StrictMode mounts the effect twice', async () => {
    respondByRoute(adapter, { 'GET /auth/me': (c) => reply(c, 200, alice) })
    renderHook(() => useAuthBootstrap(), { wrapper: StrictMode })
    await waitFor(() => expect(useAuthStore.getState().status).toBe('authenticated'))
    expect(count('GET /auth/me')).toBe(1)
  })
})

describe('useAuthBootstrap: proactive refresh', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    useAuthStore.getState().setUser(alice)
  })

  async function advance(ms: number) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms)
    })
  }

  it('refreshes every 10 minutes while authenticated', async () => {
    respondByRoute(adapter, { 'POST /auth/refresh': (c) => reply(c, 204) })
    renderHook(() => useAuthBootstrap())
    expect(REFRESH_INTERVAL_MS).toBe(10 * 60 * 1000)

    await advance(REFRESH_INTERVAL_MS - 1)
    expect(count('POST /auth/refresh')).toBe(0)
    await advance(1)
    expect(count('POST /auth/refresh')).toBe(1)
    await advance(REFRESH_INTERVAL_MS)
    expect(count('POST /auth/refresh')).toBe(2)
    expect(useAuthStore.getState().status).toBe('authenticated')
  })

  it('clears the store when a refresh fails', async () => {
    respondByRoute(adapter, {
      'POST /auth/refresh': (c) => reply(c, 401, errorBody('session_expired')),
    })
    renderHook(() => useAuthBootstrap())
    await advance(REFRESH_INTERVAL_MS)
    expect(useAuthStore.getState().status).toBe('unauthenticated')
  })

  it('stops the timer on unmount', async () => {
    respondByRoute(adapter, { 'POST /auth/refresh': (c) => reply(c, 204) })
    const { unmount } = renderHook(() => useAuthBootstrap())
    unmount()
    await advance(REFRESH_INTERVAL_MS * 3)
    expect(adapter).not.toHaveBeenCalled()
  })

  it('stops the timer on logout', async () => {
    respondByRoute(adapter, { 'POST /auth/refresh': (c) => reply(c, 204) })
    renderHook(() => useAuthBootstrap())
    act(() => useAuthStore.getState().clearUser())
    await advance(REFRESH_INTERVAL_MS * 3)
    expect(adapter).not.toHaveBeenCalled()
  })

  it('starts the timer after a login', async () => {
    useAuthStore.getState().clearUser()
    respondByRoute(adapter, { 'POST /auth/refresh': (c) => reply(c, 204) })
    renderHook(() => useAuthBootstrap())
    await advance(REFRESH_INTERVAL_MS)
    expect(adapter).not.toHaveBeenCalled()
    act(() => useAuthStore.getState().setUser(alice))
    await advance(REFRESH_INTERVAL_MS)
    expect(count('POST /auth/refresh')).toBe(1)
  })
})

describe('useAuthBootstrap: reactive refresh', () => {
  it('installs the session_expired interceptor while mounted and removes it on unmount', async () => {
    useAuthStore.getState().setUser(alice)
    let attempts = 0
    respondByRoute(adapter, {
      'GET /projects': (c) =>
        ++attempts % 2 === 1 ? reply(c, 401, errorBody('session_expired')) : reply(c, 200, []),
      'POST /auth/refresh': (c) => reply(c, 204),
    })
    const { unmount } = renderHook(() => useAuthBootstrap())
    await expect(apiClient.get('/projects')).resolves.toMatchObject({ status: 200 })
    expect(count('POST /auth/refresh')).toBe(1)

    unmount()
    await expect(apiClient.get('/projects')).rejects.toMatchObject({ code: 'session_expired' })
    expect(count('POST /auth/refresh')).toBe(1)
  })
})

describe('useAuth: actions', () => {
  it('exposes the store state', () => {
    useAuthStore.getState().setUser(alice)
    const { result } = renderHook(() => useAuth())
    expect(result.current.user).toEqual(alice)
    expect(result.current.status).toBe('authenticated')
    expect(result.current.isAuthenticated).toBe(true)
  })

  it('login stores the user and returns it', async () => {
    respondByRoute(adapter, { 'POST /auth/login': (c) => reply(c, 200, alice) })
    const { result } = renderHook(() => useAuth())
    let returned
    await act(async () => {
      returned = await result.current.login('a@example.com', 'abcd1234')
    })
    expect(returned).toEqual(alice)
    expect(result.current.isAuthenticated).toBe(true)
    expect(result.current.user).toEqual(alice)
  })

  it('a failed login leaves the store untouched and rethrows the ApiError', async () => {
    useAuthStore.getState().clearUser()
    respondByRoute(adapter, {
      'POST /auth/login': (c) => reply(c, 401, errorBody('invalid_credentials')),
    })
    const { result } = renderHook(() => useAuth())
    await act(async () => {
      await expect(result.current.login('a@example.com', 'wrong')).rejects.toMatchObject({
        code: 'invalid_credentials',
      })
    })
    expect(result.current.status).toBe('unauthenticated')
  })

  it('register returns the user without logging in', async () => {
    useAuthStore.getState().clearUser()
    respondByRoute(adapter, { 'POST /auth/register': (c) => reply(c, 201, alice) })
    const { result } = renderHook(() => useAuth())
    let returned
    await act(async () => {
      returned = await result.current.register('a@example.com', 'abcd1234')
    })
    expect(returned).toEqual(alice)
    expect(result.current.status).toBe('unauthenticated')
  })

  it('logout clears the store', async () => {
    useAuthStore.getState().setUser(alice)
    respondByRoute(adapter, { 'POST /auth/logout': (c) => reply(c, 204) })
    const { result } = renderHook(() => useAuth())
    await act(async () => {
      await result.current.logout()
    })
    expect(count('POST /auth/logout')).toBe(1)
    expect(result.current.status).toBe('unauthenticated')
    expect(result.current.user).toBeNull()
  })

  it.each([
    ['a network error', networkFailure],
    ['a server error', (c: Parameters<typeof reply>[0]) => reply(c, 500, errorBody('internal'))],
  ])('logout still clears the store after %s', async (_name, fail) => {
    useAuthStore.getState().setUser(alice)
    respondByRoute(adapter, { 'POST /auth/logout': fail })
    const { result } = renderHook(() => useAuth())
    await act(async () => {
      await result.current.logout()
    })
    expect(result.current.status).toBe('unauthenticated')
  })
})
