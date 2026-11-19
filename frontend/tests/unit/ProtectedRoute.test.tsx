import { act, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import ProtectedRoute from '../../src/components/auth/ProtectedRoute'
import { useAuthStore } from '../../src/stores/auth-store'

const alice = { id: 'u-1', email: 'a@example.com', skill_level: null }

function LoginProbe() {
  const location = useLocation()
  const from = (location.state as { from?: { pathname: string; search: string } } | null)?.from
  return <p>login page, from: {from ? `${from.pathname}${from.search}` : 'none'}</p>
}

function renderAt(path: string, children?: boolean) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<LoginProbe />} />
        {children ? (
          <Route
            path="/secret"
            element={
              <ProtectedRoute>
                <p>secret content</p>
              </ProtectedRoute>
            }
          />
        ) : (
          <Route element={<ProtectedRoute />}>
            <Route path="/secret" element={<p>secret outlet content</p>} />
          </Route>
        )}
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

describe('ProtectedRoute', () => {
  it('shows an accessible loading state and does not redirect while the status is unknown', () => {
    renderAt('/secret')
    expect(screen.getByRole('status')).toHaveTextContent('로그인 상태를 확인하는 중')
    expect(screen.queryByText(/login page/)).not.toBeInTheDocument()
    expect(screen.queryByText(/secret/)).not.toBeInTheDocument()
  })

  it('redirects an unauthenticated visitor to /login and remembers where they came from', () => {
    useAuthStore.getState().clearUser()
    renderAt('/secret?tab=2')
    expect(screen.getByText('login page, from: /secret?tab=2')).toBeInTheDocument()
  })

  it('renders its children when authenticated', () => {
    useAuthStore.getState().setUser(alice)
    renderAt('/secret', true)
    expect(screen.getByText('secret content')).toBeInTheDocument()
  })

  it('renders the nested route (Outlet) when authenticated', () => {
    useAuthStore.getState().setUser(alice)
    renderAt('/secret')
    expect(screen.getByText('secret outlet content')).toBeInTheDocument()
  })

  it('reacts when the status changes from unknown to authenticated', async () => {
    renderAt('/secret')
    expect(screen.getByRole('status')).toBeInTheDocument()
    act(() => useAuthStore.getState().setUser(alice))
    expect(await screen.findByText('secret outlet content')).toBeInTheDocument()
  })
})
