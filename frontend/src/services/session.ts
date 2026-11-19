import { isApiError, apiClient } from './api-client'
import * as authService from './auth-service'
import { useAuthStore } from '../stores/auth-store'

// Session handling on top of the cookie-based auth: refreshing an expired access token
// and finding out at start-up who (if anyone) is logged in. All outcomes are written to
// the auth store, which stays the only auth state in the app.

declare module 'axios' {
  interface AxiosRequestConfig {
    _sessionRetried?: boolean
  }
}

const SESSION_EXPIRED = 'session_expired'

let refreshInFlight: Promise<void> | null = null

// Single flight: concurrent callers wait for the same POST /auth/refresh.
export function refreshSession(): Promise<void> {
  refreshInFlight ??= authService.refresh().finally(() => {
    refreshInFlight = null
  })
  return refreshInFlight
}

// Reactive refresh: when a request fails because the access token expired (e.g. the
// computer slept and the timer never fired), refresh once and replay the request once.
// /auth/* requests are never refreshed or replayed, so this cannot loop.
export function installSessionRefresh(client = apiClient): () => void {
  const id = client.interceptors.response.use(undefined, async (error: unknown) => {
    if (!isApiError(error) || error.status !== 401 || error.code !== SESSION_EXPIRED) {
      throw error
    }
    const { config } = error
    if (!config || config.url?.startsWith('/auth/') || config._sessionRetried) throw error

    try {
      await refreshSession()
    } catch {
      useAuthStore.getState().clearUser()
      throw error
    }
    return client.request({ ...config, _sessionRetried: true })
  })
  return () => client.interceptors.response.eject(id)
}

async function resolveCurrentUser() {
  try {
    return await authService.me()
  } catch (error) {
    if (!isApiError(error) || error.code !== SESSION_EXPIRED) throw error
    await refreshSession()
    return authService.me()
  }
}

let bootstrapInFlight: Promise<void> | null = null

// Asks the server who is logged in (GET /auth/me, refreshing once if the access token
// expired). Any failure, network errors included, means "not logged in" so the app never
// stays on 'unknown'. Concurrent calls (React StrictMode) share one run.
export function bootstrapSession(): Promise<void> {
  bootstrapInFlight ??= resolveCurrentUser()
    .then((user) => useAuthStore.getState().setUser(user))
    .catch(() => useAuthStore.getState().clearUser())
    .finally(() => {
      bootstrapInFlight = null
    })
  return bootstrapInFlight
}
