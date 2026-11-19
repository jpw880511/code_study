import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import LoginForm from '../../src/components/auth/LoginForm'
import RegisterForm from '../../src/components/auth/RegisterForm'
import { ApiError } from '../../src/services/api-client'

type Submit = (values: { email: string; password: string }) => Promise<unknown>

function deferred() {
  let resolve: () => void = () => {}
  let reject: (error: unknown) => void = () => {}
  const promise = new Promise<void>((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}

const apiError = (message: string, code = 'invalid_credentials', status = 401) =>
  new ApiError({ message, code, status })

describe('LoginForm', () => {
  function setup(onSubmit: Submit = vi.fn().mockResolvedValue(undefined)) {
    const user = userEvent.setup()
    render(<LoginForm onSubmit={onSubmit} />)
    return { user, onSubmit }
  }

  it('has labelled email and password fields with the right input attributes', () => {
    setup()
    const email = screen.getByLabelText('이메일')
    const password = screen.getByLabelText('비밀번호')
    expect(email).toHaveAttribute('type', 'email')
    expect(email).toHaveAttribute('autocomplete', 'email')
    expect(password).toHaveAttribute('type', 'password')
    expect(password).toHaveAttribute('autocomplete', 'current-password')
    expect(screen.getByRole('button', { name: '로그인' })).toBeEnabled()
  })

  it('submits the typed credentials', async () => {
    const { user, onSubmit } = setup()
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({
      email: 'a@example.com',
      password: 'abcd1234',
    })
  })

  it('trims the email before submitting', async () => {
    const { user, onSubmit } = setup()
    await user.type(screen.getByLabelText('이메일'), '  a@example.com  ')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(onSubmit).toHaveBeenCalledWith({ email: 'a@example.com', password: 'abcd1234' })
  })

  it('requires both fields and does not submit', async () => {
    const { user, onSubmit } = setup()
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(screen.getByText('이메일을 입력하세요.')).toBeInTheDocument()
    expect(screen.getByText('비밀번호를 입력하세요.')).toBeInTheDocument()
    expect(screen.getByLabelText('이메일')).toBeInvalid()
    expect(screen.getByLabelText('이메일')).toHaveAccessibleDescription('이메일을 입력하세요.')
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects a malformed email', async () => {
    const { user, onSubmit } = setup()
    await user.type(screen.getByLabelText('이메일'), 'not-an-email')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(screen.getByText('올바른 이메일 형식이 아닙니다.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows the server error message in an alert', async () => {
    const { user } = setup(
      vi.fn().mockRejectedValue(apiError('이메일 또는 비밀번호가 올바르지 않습니다.')),
    )
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '이메일 또는 비밀번호가 올바르지 않습니다.',
    )
    expect(screen.getByRole('button', { name: '로그인' })).toBeEnabled()
  })

  it('shows a generic message for an unexpected error', async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error('boom')))
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('로그인하지 못했습니다')
  })

  it('clears the previous server error on the next attempt', async () => {
    const onSubmit = vi
      .fn()
      .mockRejectedValueOnce(apiError('틀렸습니다.'))
      .mockResolvedValue(undefined)
    const { user } = setup(onSubmit)
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: '로그인' }))
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
  })

  it('disables the button while submitting and ignores a second submit', async () => {
    const pending = deferred()
    const { user, onSubmit } = setup(vi.fn().mockReturnValue(pending.promise))
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234{Enter}')

    const button = screen.getByRole('button', { name: '로그인 중...' })
    expect(button).toBeDisabled()
    await user.type(screen.getByLabelText('비밀번호'), '{Enter}')
    await user.click(button)
    fireEvent.submit(screen.getByLabelText('이메일').closest('form')!)
    expect(onSubmit).toHaveBeenCalledTimes(1)

    pending.resolve()
    await waitFor(() => expect(screen.getByRole('button', { name: '로그인' })).toBeEnabled())
  })
})

describe('RegisterForm', () => {
  function setup(onSubmit: Submit = vi.fn().mockResolvedValue(undefined)) {
    const user = userEvent.setup()
    render(<RegisterForm onSubmit={onSubmit} />)
    return { user, onSubmit }
  }

  async function fill(
    user: ReturnType<typeof userEvent.setup>,
    values: { email?: string; password?: string; confirm?: string },
  ) {
    if (values.email) await user.type(screen.getByLabelText('이메일'), values.email)
    if (values.password) await user.type(screen.getByLabelText('비밀번호'), values.password)
    if (values.confirm) await user.type(screen.getByLabelText('비밀번호 확인'), values.confirm)
  }

  const submit = (user: ReturnType<typeof userEvent.setup>) =>
    user.click(screen.getByRole('button', { name: '회원가입' }))

  it('has three labelled fields with the right input attributes', () => {
    setup()
    expect(screen.getByLabelText('이메일')).toHaveAttribute('autocomplete', 'email')
    for (const label of ['비밀번호', '비밀번호 확인']) {
      const field = screen.getByLabelText(label)
      expect(field).toHaveAttribute('type', 'password')
      expect(field).toHaveAttribute('autocomplete', 'new-password')
    }
  })

  it('submits email and password (not the confirmation)', async () => {
    const { user, onSubmit } = setup()
    await fill(user, { email: ' A@Example.com ', password: 'abcd1234', confirm: 'abcd1234' })
    await submit(user)
    expect(onSubmit).toHaveBeenCalledExactlyOnceWith({
      email: 'A@Example.com',
      password: 'abcd1234',
    })
  })

  it('requires every field', async () => {
    const { user, onSubmit } = setup()
    await submit(user)
    expect(screen.getByText('이메일을 입력하세요.')).toBeInTheDocument()
    expect(screen.getByText('비밀번호를 입력하세요.')).toBeInTheDocument()
    expect(screen.getByText('비밀번호 확인을 입력하세요.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('rejects a malformed email', async () => {
    const { user, onSubmit } = setup()
    await fill(user, { email: 'a@b', password: 'abcd1234', confirm: 'abcd1234' })
    await submit(user)
    expect(screen.getByText('올바른 이메일 형식이 아닙니다.')).toBeInTheDocument()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it.each([
    ['abc1234', '비밀번호는 8자 이상이어야 합니다.'],
    ['12345678', '비밀번호에 영문자를 포함하세요.'],
    ['abcdefgh', '비밀번호에 숫자를 포함하세요.'],
    ['가'.repeat(24) + 'a1', '비밀번호는 72바이트 이하여야 합니다. (한글은 글자당 3바이트)'],
  ])('rejects the password "%s"', async (password, message) => {
    const { user, onSubmit } = setup()
    await fill(user, { email: 'a@example.com', password, confirm: password })
    await submit(user)
    expect(screen.getByText(message)).toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호')).toBeInvalid()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('accepts exactly 72 bytes', async () => {
    const password = 'a1'.repeat(36)
    const { user, onSubmit } = setup()
    await fill(user, { email: 'a@example.com', password, confirm: password })
    await submit(user)
    expect(onSubmit).toHaveBeenCalledTimes(1)
  })

  it('requires the confirmation to match', async () => {
    const { user, onSubmit } = setup()
    await fill(user, { email: 'a@example.com', password: 'abcd1234', confirm: 'abcd12345' })
    await submit(user)
    expect(screen.getByText('비밀번호가 일치하지 않습니다.')).toBeInTheDocument()
    expect(screen.getByLabelText('비밀번호 확인')).toBeInvalid()
    expect(onSubmit).not.toHaveBeenCalled()
  })

  it('shows the server error message in an alert and re-enables the button', async () => {
    const error = apiError('이미 가입된 이메일입니다.', 'email_already_registered', 409)
    const { user } = setup(vi.fn().mockRejectedValue(error))
    await fill(user, { email: 'a@example.com', password: 'abcd1234', confirm: 'abcd1234' })
    await submit(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 가입된 이메일입니다.')
    expect(screen.getByRole('button', { name: '회원가입' })).toBeEnabled()
  })

  it('shows a generic message for an unexpected error', async () => {
    const { user } = setup(vi.fn().mockRejectedValue(new Error('boom')))
    await fill(user, { email: 'a@example.com', password: 'abcd1234', confirm: 'abcd1234' })
    await submit(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('회원가입하지 못했습니다')
  })

  it('disables the button while submitting and ignores a second submit', async () => {
    const pending = deferred()
    const { user, onSubmit } = setup(vi.fn().mockReturnValue(pending.promise))
    await fill(user, { email: 'a@example.com', password: 'abcd1234', confirm: 'abcd1234' })
    await submit(user)

    const button = screen.getByRole('button', { name: '가입 중...' })
    expect(button).toBeDisabled()
    await user.type(screen.getByLabelText('비밀번호 확인'), '{Enter}')
    await user.click(button)
    fireEvent.submit(screen.getByLabelText('이메일').closest('form')!)
    expect(onSubmit).toHaveBeenCalledTimes(1)

    pending.resolve()
    await waitFor(() => expect(screen.getByRole('button', { name: '회원가입' })).toBeEnabled())
  })
})
