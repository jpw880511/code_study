import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import { validateEmail, validateLoginPassword } from '../../lib/auth-validation'
import FormField from './FormField'
import { useFormSubmission } from './useFormSubmission'

export interface Credentials {
  email: string
  password: string
}

interface LoginFormProps {
  onSubmit: (credentials: Credentials) => Promise<unknown>
}

export default function LoginForm({ onSubmit }: LoginFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const { pending, serverError, submit } = useFormSubmission(
    '로그인하지 못했습니다. 잠시 후 다시 시도하세요.',
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedEmail = email.trim()
    const found = {
      email: validateEmail(trimmedEmail),
      password: validateLoginPassword(password),
    }
    setErrors(found)
    if (found.email || found.password) return
    void submit(() => onSubmit({ email: trimmedEmail, password }))
  }

  return (
    <Card>
      <CardContent>
        <form noValidate onSubmit={handleSubmit} className="grid gap-4">
          {serverError && (
            <p role="alert" className="text-sm text-destructive">
              {serverError}
            </p>
          )}
          <FormField
            id="login-email"
            label="이메일"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={errors.email}
          />
          <FormField
            id="login-password"
            label="비밀번호"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={errors.password}
          />
          <Button type="submit" disabled={pending}>
            {pending ? '로그인 중...' : '로그인'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
