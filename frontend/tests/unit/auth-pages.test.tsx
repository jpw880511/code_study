import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import Login from '../../src/pages/Login'
import Register from '../../src/pages/Register'
import { useAuthStore } from '../../src/stores/auth-store'
import { errorBody, reply, requestKey, respondByRoute, mockApi } from '../helpers/mock-api'

const adapter = mockApi()
const alice = { id: 'u-1', email: 'a@example.com', skill_level: null }

function Where() {
  const { pathname, search } = useLocation()
  return <p>now at {pathname + search}</p>
}

function renderAt(entry: string | { pathname: string; state?: unknown }) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="*" element={<Where />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  useAuthStore.getState().clearUser()
})

describe('Login page', () => {
  async function logIn(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
  }

  it('has a level-1 heading and a link to the register page', () => {
    renderAt('/login')
    expect(screen.getByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '회원가입' })).toHaveAttribute('href', '/register')
  })

  it('shows no registration notice by default', () => {
    renderAt('/login')
    expect(screen.queryByText('회원가입이 완료되었습니다. 로그인하세요.')).not.toBeInTheDocument()
  })

  it('shows the registration notice when arriving from the register page', () => {
    renderAt({ pathname: '/login', state: { registered: true } })
    expect(screen.getByRole('status')).toHaveTextContent('회원가입이 완료되었습니다. 로그인하세요.')
  })

  it('stores the user and goes to the dashboard after a successful login', async () => {
    respondByRoute(adapter, { 'POST /auth/login': (c) => reply(c, 200, alice) })
    const user = userEvent.setup()
    renderAt('/login')
    await logIn(user)
    expect(await screen.findByText('now at /')).toBeInTheDocument()
    expect(useAuthStore.getState().user).toEqual(alice)
    expect(useAuthStore.getState().status).toBe('authenticated')
    const body = JSON.parse(adapter.mock.calls[0][0].data)
    expect(body).toEqual({ email: 'a@example.com', password: 'abcd1234' })
  })

  it('goes back to the page the user originally wanted', async () => {
    respondByRoute(adapter, { 'POST /auth/login': (c) => reply(c, 200, alice) })
    const user = userEvent.setup()
    renderAt({
      pathname: '/login',
      state: { from: { pathname: '/projects/p1', search: '?tab=2', hash: '' } },
    })
    await logIn(user)
    expect(await screen.findByText('now at /projects/p1?tab=2')).toBeInTheDocument()
  })

  it('shows the server error and stays on the page when the login fails', async () => {
    respondByRoute(adapter, {
      'POST /auth/login': (c) =>
        reply(
          c,
          401,
          errorBody('invalid_credentials', '이메일 또는 비밀번호가 올바르지 않습니다.'),
        ),
    })
    const user = userEvent.setup()
    renderAt('/login')
    await logIn(user)
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '이메일 또는 비밀번호가 올바르지 않습니다.',
    )
    expect(screen.getByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
    expect(useAuthStore.getState().status).toBe('unauthenticated')
  })

  it('redirects an authenticated visitor to the dashboard', () => {
    useAuthStore.getState().setUser(alice)
    renderAt('/login')
    expect(screen.getByText('now at /')).toBeInTheDocument()
  })

  it('does not decide anything while the status is unknown', () => {
    useAuthStore.setState(useAuthStore.getInitialState(), true)
    renderAt('/login')
    expect(screen.getByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
  })
})

describe('Register page', () => {
  async function register(user: ReturnType<typeof userEvent.setup>) {
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.type(screen.getByLabelText('비밀번호 확인'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '회원가입' }))
  }

  it('has a level-1 heading and a link to the login page', () => {
    renderAt('/register')
    expect(screen.getByRole('heading', { level: 1, name: '회원가입' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: '로그인' })).toHaveAttribute('href', '/login')
  })

  it('goes to the login page with the notice after registering, without logging in', async () => {
    respondByRoute(adapter, { 'POST /auth/register': (c) => reply(c, 201, alice) })
    const user = userEvent.setup()
    renderAt('/register')
    await register(user)
    expect(await screen.findByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('회원가입이 완료되었습니다. 로그인하세요.')
    expect(useAuthStore.getState().status).toBe('unauthenticated')
    expect(requestKey(adapter.mock.calls[0][0])).toBe('POST /auth/register')
  })

  it('shows the server error and stays on the page when registration fails', async () => {
    respondByRoute(adapter, {
      'POST /auth/register': (c) =>
        reply(c, 409, errorBody('email_already_registered', '이미 가입된 이메일입니다.')),
    })
    const user = userEvent.setup()
    renderAt('/register')
    await register(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('이미 가입된 이메일입니다.')
    await waitFor(() =>
      expect(screen.getByRole('heading', { level: 1, name: '회원가입' })).toBeInTheDocument(),
    )
  })

  it('redirects an authenticated visitor to the dashboard', () => {
    useAuthStore.getState().setUser(alice)
    renderAt('/register')
    expect(screen.getByText('now at /')).toBeInTheDocument()
  })
})
