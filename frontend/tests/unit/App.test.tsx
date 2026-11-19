import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import App, { AppRoutes } from '../../src/App'
import { createQueryClient } from '../../src/lib/queryClient'
import { useAuthStore } from '../../src/stores/auth-store'
import { errorBody, reply, requestKey, respondByRoute, mockApi } from '../helpers/mock-api'
import { makeProject } from '../helpers/project-fixtures'
import { makeTaskDetail } from '../helpers/task-fixtures'

const adapter = mockApi()
const alice = { id: 'u-1', email: 'a@example.com', skill_level: null }

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  answerProjects()
})

function logIn() {
  useAuthStore.getState().setUser(alice)
}

function logOut() {
  useAuthStore.getState().clearUser()
}

// The dashboard and project pages load data, so pages are rendered with a query client.
// Unless a test installs its own handlers the project API answers with an empty list and
// one known project.
function answerProjects() {
  respondByRoute(adapter, {
    'GET /projects': (c) => reply(c, 200, []),
    'GET /projects/abc-123': (c) =>
      reply(c, 200, makeProject({ id: 'abc-123', title: '라우팅 프로젝트' })),
    'GET /projects/abc-123/tasks': (c) => reply(c, 200, []),
    'GET /tasks/t-77': (c) => reply(c, 200, makeTaskDetail({ id: 't-77', title: '라우팅 Task' })),
  })
}

function renderAt(path: string) {
  return render(
    <QueryClientProvider client={createQueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <AppRoutes />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

describe('route structure (authenticated)', () => {
  beforeEach(logIn)

  it.each([
    ['/', '대시보드'],
    ['/trash', '휴지통'],
  ])('renders %s with the "%s" page', (path, heading) => {
    renderAt(path)
    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  it('renders the project page for the project id from the URL', async () => {
    renderAt('/projects/abc-123')
    expect(
      await screen.findByRole('heading', { level: 1, name: '라우팅 프로젝트' }),
    ).toBeInTheDocument()
    expect(requestKey(adapter.mock.calls[0][0])).toBe('GET /projects/abc-123')
  })

  it('shows the project error on the project page when the project is missing', async () => {
    respondByRoute(adapter, {
      'GET /projects/gone': (c) =>
        reply(c, 404, errorBody('project_not_found', '요청한 프로젝트를 찾을 수 없습니다.')),
    })
    renderAt('/projects/gone')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '요청한 프로젝트를 찾을 수 없습니다.',
    )
  })

  it('lists the projects on the dashboard', async () => {
    respondByRoute(adapter, {
      'GET /projects': (c) => reply(c, 200, [makeProject({ id: 'x', title: '목록 프로젝트' })]),
    })
    renderAt('/')
    expect(await screen.findByRole('link', { name: /목록 프로젝트/ })).toHaveAttribute(
      'href',
      '/projects/x',
    )
  })

  it('renders the task page for the task id from the URL', async () => {
    renderAt('/tasks/t-77')
    expect(
      await screen.findByRole('heading', { level: 1, name: '라우팅 Task' }),
    ).toBeInTheDocument()
    expect(requestKey(adapter.mock.calls[0][0])).toBe('GET /tasks/t-77')
  })

  it('renders a not-found page for unknown URLs', () => {
    renderAt('/does/not/exist')
    expect(
      screen.getByRole('heading', { level: 1, name: '페이지를 찾을 수 없습니다' }),
    ).toBeInTheDocument()
  })

  it('does not match the old nested task URL', () => {
    renderAt('/projects/abc-123/tasks/7')
    expect(
      screen.getByRole('heading', { level: 1, name: '페이지를 찾을 수 없습니다' }),
    ).toBeInTheDocument()
  })
})

describe('public auth pages', () => {
  beforeEach(logOut)

  it.each([
    ['/login', '로그인'],
    ['/register', '회원가입'],
  ])('renders %s with the "%s" page without being logged in', (path, heading) => {
    renderAt(path)
    expect(screen.getByRole('heading', { level: 1, name: heading })).toBeInTheDocument()
  })

  it.each(['/login', '/register'])('redirects an authenticated visitor from %s to /', (path) => {
    logIn()
    renderAt(path)
    expect(screen.getByRole('heading', { level: 1, name: '대시보드' })).toBeInTheDocument()
  })

  it.each(['/dev/query-demo', '/dev-test'])('keeps the dev page %s public', (path) => {
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter initialEntries={[path]}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(screen.getByRole('heading', { level: 1 })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { level: 1, name: '로그인' })).not.toBeInTheDocument()
  })
})

describe('protected routes', () => {
  it.each(['/', '/trash', '/projects/p1', '/tasks/1', '/does/not/exist'])(
    'redirects %s to the login page when unauthenticated',
    (path) => {
      logOut()
      renderAt(path)
      expect(screen.getByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
    },
  )

  it('shows a loading state, not the login page, while the status is unknown', () => {
    renderAt('/trash')
    expect(screen.getByRole('status')).toHaveTextContent('로그인 상태를 확인하는 중')
    expect(screen.queryByRole('heading', { level: 1, name: '로그인' })).not.toBeInTheDocument()
  })

  it('sends the user back to the wanted page after logging in', async () => {
    logOut()
    respondByRoute(adapter, { 'POST /auth/login': (c) => reply(c, 200, alice) })
    const user = userEvent.setup()
    renderAt('/trash')
    await user.type(screen.getByLabelText('이메일'), 'a@example.com')
    await user.type(screen.getByLabelText('비밀번호'), 'abcd1234')
    await user.click(screen.getByRole('button', { name: '로그인' }))
    expect(await screen.findByRole('heading', { level: 1, name: '휴지통' })).toBeInTheDocument()
  })
})

describe('logout button', () => {
  it('is shown in the navigation bar only when authenticated', () => {
    logIn()
    renderAt('/')
    expect(screen.getByRole('button', { name: '로그아웃' })).toBeInTheDocument()
  })

  it.each(['unknown', 'unauthenticated'] as const)('is hidden when the status is %s', (status) => {
    if (status === 'unauthenticated') logOut()
    renderAt('/dev-test')
    expect(screen.queryByRole('button', { name: '로그아웃' })).not.toBeInTheDocument()
  })

  it('logs out through the server and returns to the login page', async () => {
    logIn()
    respondByRoute(adapter, {
      'GET /projects': (c) => reply(c, 200, []),
      'POST /auth/logout': (c) => reply(c, 204),
    })
    const user = userEvent.setup()
    renderAt('/')
    await user.click(screen.getByRole('button', { name: '로그아웃' }))
    expect(await screen.findByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
    expect(adapter.mock.calls.map(([c]) => requestKey(c))).toContain('POST /auth/logout')
    expect(useAuthStore.getState().status).toBe('unauthenticated')
  })
})

describe('navigation bar', () => {
  beforeEach(logIn)

  it.each(['/', '/trash', '/projects/p1', '/tasks/1', '/unknown'])('is shown on %s', (path) => {
    renderAt(path)
    expect(screen.getByRole('navigation')).toBeInTheDocument()
  })

  it.each(['/login', '/register'])('is hidden on %s', (path) => {
    logOut()
    renderAt(path)
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument()
  })

  it('links to the dashboard and the trash', () => {
    renderAt('/trash')
    expect(screen.getByRole('link', { name: '대시보드' })).toHaveAttribute('href', '/')
    expect(screen.getByRole('link', { name: '휴지통' })).toHaveAttribute('href', '/trash')
  })

  it('navigates between pages without a reload', async () => {
    const user = userEvent.setup()
    renderAt('/')
    await user.click(screen.getByRole('link', { name: '휴지통' }))
    expect(screen.getByRole('heading', { level: 1, name: '휴지통' })).toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: '대시보드' }))
    expect(screen.getByRole('heading', { level: 1, name: '대시보드' })).toBeInTheDocument()
  })
})

describe('App', () => {
  it('reads the browser URL (BrowserRouter)', () => {
    logOut()
    window.history.pushState({}, '', '/login')
    render(<App />)
    expect(screen.getByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
  })

  it('asks the server who is logged in on start-up and shows the wanted page', async () => {
    respondByRoute(adapter, { 'GET /auth/me': (c) => reply(c, 200, alice) })
    window.history.pushState({}, '', '/trash')
    render(<App />)
    expect(await screen.findByRole('heading', { level: 1, name: '휴지통' })).toBeInTheDocument()
  })

  it('goes to the login page on start-up when nobody is logged in', async () => {
    respondByRoute(adapter, {
      'GET /auth/me': (c) =>
        reply(c, 401, { error: 'not_authenticated', message: '로그인이 필요합니다.' }),
    })
    window.history.pushState({}, '', '/trash')
    render(<App />)
    expect(await screen.findByRole('heading', { level: 1, name: '로그인' })).toBeInTheDocument()
  })
})
