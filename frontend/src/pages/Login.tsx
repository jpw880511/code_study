import { Link, Navigate, useLocation, type To } from 'react-router-dom'

import LoginForm from '../components/auth/LoginForm'
import { useAuth } from '../hooks/useAuth'

interface LoginLocationState {
  from?: To
  registered?: boolean
}

export default function Login() {
  const { isAuthenticated, login } = useAuth()
  const state = useLocation().state as LoginLocationState | null

  // Logging in flips isAuthenticated, so this redirect also performs the post-login
  // navigation: back to the page the user originally wanted, or to the dashboard.
  if (isAuthenticated) return <Navigate to={state?.from ?? '/'} replace />

  return (
    <main className="mx-auto grid max-w-sm gap-4 p-4">
      <h1 className="text-2xl font-semibold">로그인</h1>
      {state?.registered && <p role="status">회원가입이 완료되었습니다. 로그인하세요.</p>}
      <LoginForm onSubmit={({ email, password }) => login(email, password)} />
      <p className="text-sm">
        계정이 없으신가요?{' '}
        <Link to="/register" className="underline">
          회원가입
        </Link>
      </p>
    </main>
  )
}
