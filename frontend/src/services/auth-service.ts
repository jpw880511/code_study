import type { AuthUser } from '../stores/auth-store'
import { apiClient } from './api-client'

// Thin typed wrappers over the /auth endpoints. The server keeps the tokens in HTTP-only
// cookies, so nothing here touches the auth store: callers decide how to react.

export async function register(email: string, password: string): Promise<AuthUser> {
  const { data } = await apiClient.post<AuthUser>('/auth/register', { email, password })
  return data
}

export async function login(email: string, password: string): Promise<AuthUser> {
  const { data } = await apiClient.post<AuthUser>('/auth/login', { email, password })
  return data
}

export async function me(): Promise<AuthUser> {
  const { data } = await apiClient.get<AuthUser>('/auth/me')
  return data
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout')
}

export async function refresh(): Promise<void> {
  await apiClient.post('/auth/refresh')
}
