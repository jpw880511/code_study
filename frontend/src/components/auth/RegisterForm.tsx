import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Card, CardContent } from '@/components/ui/card'
import {
  validateEmail,
  validateNewPassword,
  validatePasswordConfirmation,
} from '../../lib/auth-validation'
import FormField from './FormField'
import type { Credentials } from './LoginForm'
import { useFormSubmission } from './useFormSubmission'

interface RegisterFormProps {
  onSubmit: (credentials: Credentials) => Promise<unknown>
}

export default function RegisterForm({ onSubmit }: RegisterFormProps) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmation, setConfirmation] = useState('')
  const [errors, setErrors] = useState<{
    email?: string
    password?: string
    confirmation?: string
  }>({})
  const { pending, serverError, submit } = useFormSubmission(
    '회원가입하지 못했습니다. 잠시 후 다시 시도하세요.',
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const trimmedEmail = email.trim()
    const found = {
      email: validateEmail(trimmedEmail),
      password: validateNewPassword(password),
      confirmation: validatePasswordConfirmation(password, confirmation),
    }
    setErrors(found)
    if (found.email || found.password || found.confirmation) return
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
            id="register-email"
            label="이메일"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={errors.email}
          />
          <FormField
            id="register-password"
            label="비밀번호"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            error={errors.password}
          />
          <FormField
            id="register-password-confirmation"
            label="비밀번호 확인"
            type="password"
            autoComplete="new-password"
            value={confirmation}
            onChange={(event) => setConfirmation(event.target.value)}
            error={errors.confirmation}
          />
          <Button type="submit" disabled={pending}>
            {pending ? '가입 중...' : '회원가입'}
          </Button>
        </form>
      </CardContent>
    </Card>
  )
}
