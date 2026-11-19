import { Link, Navigate, useNavigate } from 'react-router-dom'

import RegisterForm from '../components/auth/RegisterForm'
import { useAuth } from '../hooks/useAuth'

export default function Register() {
  const { isAuthenticated, register } = useAuth()
  const navigate = useNavigate()

  if (isAuthenticated) return <Navigate to="/" replace />

  async function handleSubmit({ email, password }: { email: string; password: string }) {
    await register(email, password)
    navigate('/login', { state: { registered: true } })
  }

  return (
    <main className="mx-auto grid max-w-sm gap-4 p-4">
      <h1 className="text-2xl font-semibold">회원가입</h1>
      <RegisterForm onSubmit={handleSubmit} />
      <p className="text-sm">
        이미 계정이 있으신가요?{' '}
        <Link to="/login" className="underline">
          로그인
        </Link>
      </p>
    </main>
  )
}
