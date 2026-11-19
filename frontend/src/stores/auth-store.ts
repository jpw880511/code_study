import { create } from 'zustand'

// The JWTs travel in HTTP-only cookies that JavaScript cannot read, so this store keeps
// only who is logged in. It is deliberately not persisted: after a page load the app asks
// the server (GET /auth/me) and the cookie remains the single source of truth.

export interface AuthUser {
  id: string
  email: string
  skill_level: string | null
}

// 'unknown' lasts until the server has answered, so route guards do not redirect too early.
export type AuthStatus = 'unknown' | 'authenticated' | 'unauthenticated'

interface AuthState {
  user: AuthUser | null
  status: AuthStatus
  setUser: (user: AuthUser) => void
  clearUser: () => void
}

export const useAuthStore = create<AuthState>()((set) => ({
  user: null,
  status: 'unknown',
  setUser: (user) => set({ user, status: 'authenticated' }),
  clearUser: () => set({ user: null, status: 'unauthenticated' }),
}))

export const selectIsAuthenticated = (state: AuthState) => state.status === 'authenticated'
