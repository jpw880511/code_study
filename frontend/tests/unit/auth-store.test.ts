import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it } from 'vitest'

import { selectIsAuthenticated, useAuthStore, type AuthUser } from '../../src/stores/auth-store'

const alice: AuthUser = { id: 'u-1', email: 'alice@example.com', skill_level: 'Complete Beginner' }
const bob: AuthUser = { id: 'u-2', email: 'bob@example.com', skill_level: 'Intermediate' }

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

afterEach(() => {
  localStorage.clear()
  sessionStorage.clear()
})

describe('initial state', () => {
  it('does not know yet whether the visitor is logged in', () => {
    const { user, status } = useAuthStore.getState()
    expect(user).toBeNull()
    expect(status).toBe('unknown')
    expect(selectIsAuthenticated(useAuthStore.getState())).toBe(false)
  })
})

describe('setUser', () => {
  it('stores the user and marks the visitor as authenticated', () => {
    useAuthStore.getState().setUser(alice)
    const state = useAuthStore.getState()
    expect(state.user).toEqual(alice)
    expect(state.status).toBe('authenticated')
    expect(selectIsAuthenticated(state)).toBe(true)
  })

  it('replaces the previous user', () => {
    useAuthStore.getState().setUser(alice)
    useAuthStore.getState().setUser(bob)
    expect(useAuthStore.getState().user).toEqual(bob)
  })
})

describe('clearUser', () => {
  it('forgets the user and marks the visitor as not logged in', () => {
    useAuthStore.getState().setUser(alice)
    useAuthStore.getState().clearUser()
    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.status).toBe('unauthenticated')
    expect(selectIsAuthenticated(state)).toBe(false)
  })

  it('also settles the "unknown" state (the server said nobody is logged in)', () => {
    useAuthStore.getState().clearUser()
    expect(useAuthStore.getState().status).toBe('unauthenticated')
  })
})

describe('selectIsAuthenticated', () => {
  it.each([
    ['unknown', false],
    ['unauthenticated', false],
    ['authenticated', true],
  ] as const)('is %s -> %s', (status, expected) => {
    expect(selectIsAuthenticated({ ...useAuthStore.getState(), status })).toBe(expected)
  })
})

describe('security decisions', () => {
  it('never holds tokens: the JWTs live in HTTP-only cookies', () => {
    const keys = Object.keys(useAuthStore.getState())
    expect(keys.filter((key) => /token|jwt|secret|password/i.test(key))).toEqual([])
  })

  it('does not copy the user into browser storage', () => {
    useAuthStore.getState().setUser(alice)
    expect(localStorage.length).toBe(0)
    expect(sessionStorage.length).toBe(0)
  })
})

describe('React usage', () => {
  it('re-renders a subscribed component when the user changes', () => {
    const { result } = renderHook(() => useAuthStore(selectIsAuthenticated))
    expect(result.current).toBe(false)

    act(() => useAuthStore.getState().setUser(alice))
    expect(result.current).toBe(true)

    act(() => useAuthStore.getState().clearUser())
    expect(result.current).toBe(false)
  })

  it('exposes the actions to components', () => {
    const { result } = renderHook(() => useAuthStore())
    act(() => result.current.setUser(bob))
    expect(result.current.user).toEqual(bob)
  })

  it('can be updated outside React (for example from an HTTP interceptor)', () => {
    useAuthStore.getState().setUser(alice)
    useAuthStore.getState().clearUser()
    expect(useAuthStore.getState().user).toBeNull()
  })
})
