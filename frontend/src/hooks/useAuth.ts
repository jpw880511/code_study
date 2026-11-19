import { useCallback, useEffect } from 'react'

import * as authService from '../services/auth-service'
import { bootstrapSession, installSessionRefresh, refreshSession } from '../services/session'
import { selectIsAuthenticated, useAuthStore } from '../stores/auth-store'

// The access token lives 15 minutes; refreshing every 10 keeps a safety margin.
export const REFRESH_INTERVAL_MS = 10 * 60 * 1000

// Session lifecycle. Mount it exactly once, at the top of the app (see AuthProvider):
//  - asks the server who is logged in while the status is still 'unknown'
//  - refreshes the tokens periodically while authenticated
//  - refreshes and replays a request that failed because the access token expired
export function useAuthBootstrap(): void {
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  useEffect(() => {
    if (useAuthStore.getState().status === 'unknown') void bootstrapSession()
  }, [])

  useEffect(() => installSessionRefresh(), [])

  useEffect(() => {
    if (!isAuthenticated) return
    const timer = setInterval(() => {
      refreshSession().catch(() => useAuthStore.getState().clearUser())
    }, REFRESH_INTERVAL_MS)
    return () => clearInterval(timer)
  }, [isAuthenticated])
}

// Read access to the auth state plus the login/register/logout actions.
export function useAuth() {
  const user = useAuthStore((state) => state.user)
  const status = useAuthStore((state) => state.status)
  const isAuthenticated = useAuthStore(selectIsAuthenticated)

  const login = useCallback(async (email: string, password: string) => {
    const loggedIn = await authService.login(email, password)
    useAuthStore.getState().setUser(loggedIn)
    return loggedIn
  }, [])

  // Registering does not log in: the server sets no cookies.
  const register = useCallback(
    (email: string, password: string) => authService.register(email, password),
    [],
  )

  // The user must always end up logged out locally, even if the server cannot be reached.
  const logout = useCallback(async () => {
    try {
      await authService.logout()
    } catch {
      // nothing to recover: the cookies expire on their own
    } finally {
      useAuthStore.getState().clearUser()
    }
  }, [])

  return { user, status, isAuthenticated, login, register, logout }
}
