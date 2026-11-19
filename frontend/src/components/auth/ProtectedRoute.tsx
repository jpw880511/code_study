import type { ReactNode } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { useAuthStore } from '../../stores/auth-store'

interface ProtectedRouteProps {
  children?: ReactNode
}

// Guards routes that need a logged-in user. While the server has not answered yet
// ('unknown') it only shows a loading state: redirecting then would send every page
// reload to the login page.
export default function ProtectedRoute({ children }: ProtectedRouteProps) {
  const status = useAuthStore((state) => state.status)
  const location = useLocation()

  if (status === 'unknown') {
    return (
      <div role="status" aria-live="polite">
        로그인 상태를 확인하는 중...
      </div>
    )
  }
  if (status === 'unauthenticated') {
    return <Navigate to="/login" replace state={{ from: location }} />
  }
  return children ?? <Outlet />
}
