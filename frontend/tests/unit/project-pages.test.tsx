import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { createQueryClient } from '../../src/lib/queryClient'
import Dashboard from '../../src/pages/Dashboard'
import ProjectDetail from '../../src/pages/ProjectDetail'
import { useAuthStore } from '../../src/stores/auth-store'
import { errorBody, mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import { makeProject } from '../helpers/project-fixtures'

const adapter = mockApi()

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
  useAuthStore.getState().setUser({ id: 'u-1', email: 'a@example.com', skill_level: null })
})

function renderApp(path: string) {
  const client = createQueryClient()
  client.setDefaultOptions({
    ...client.getDefaultOptions(),
    queries: { ...client.getDefaultOptions().queries, retryDelay: 0 },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/projects/:projectId" element={<ProjectDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function calls() {
  return adapter.mock.calls.map(([c]) => requestKey(c))
}

describe('Dashboard', () => {
  it('shows a loading status first', () => {
    adapter.mockImplementation(() => new Promise(() => undefined))
    renderApp('/')
    expect(screen.getByRole('heading', { level: 1, name: '대시보드' })).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent('프로젝트를 불러오는 중')
  })

  it('shows the empty state with its own "새 프로젝트" button', async () => {
    respondByRoute(adapter, { 'GET /projects': (c) => reply(c, 200, []) })
    renderApp('/')
    expect(
      await screen.findByText('아직 프로젝트가 없습니다. 첫 프로젝트를 만들어 보세요.'),
    ).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: '새 프로젝트' })).toHaveLength(2)
  })

  it('shows the projects in a responsive grid of cards', async () => {
    respondByRoute(adapter, {
      'GET /projects': (c) =>
        reply(c, 200, [
          makeProject({ id: 'a', title: '첫째' }),
          makeProject({ id: 'b', title: '둘째' }),
        ]),
    })
    renderApp('/')
    const list = await screen.findByRole('list', { name: '프로젝트 목록' })
    expect(list).toHaveClass('grid', 'grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3')
    expect(
      within(list)
        .getAllByRole('link')
        .map((l) => l.getAttribute('href')),
    ).toEqual(['/projects/a', '/projects/b'])
    expect(screen.getAllByRole('button', { name: '새 프로젝트' })).toHaveLength(1)
    expect(screen.queryByText(/아직 프로젝트가 없습니다/)).not.toBeInTheDocument()
  })

  it('shows the error message and retries', async () => {
    let attempts = 0
    respondByRoute(adapter, {
      'GET /projects': (c) => {
        attempts += 1
        return attempts <= 1
          ? reply(c, 400, errorBody('bad', '불러오지 못했습니다.'))
          : reply(c, 200, [makeProject()])
      },
    })
    const user = userEvent.setup()
    renderApp('/')
    expect(await screen.findByRole('alert')).toHaveTextContent('불러오지 못했습니다.')
    await user.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(await screen.findByText('알고리즘 스터디')).toBeInTheDocument()
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })

  it('falls back to a generic message for non-API errors', async () => {
    adapter.mockRejectedValue(new Error('boom'))
    renderApp('/')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '프로젝트를 불러오지 못했습니다. 잠시 후 다시 시도하세요.',
    )
  })

  describe('creation flow', () => {
    function mockServer() {
      let list = [makeProject({ id: 'old', title: '기존 프로젝트' })]
      respondByRoute(adapter, {
        'GET /projects': (c) => reply(c, 200, list),
        'POST /projects': (c) => {
          const body = JSON.parse(c.data as string) as { title: string }
          const created = makeProject({ id: 'new', title: body.title })
          list = [created, ...list]
          return reply(c, 201, created)
        },
      })
    }

    it('opens the modal from the header button, creates, closes and lists the new project', async () => {
      mockServer()
      const user = userEvent.setup()
      renderApp('/')
      await screen.findByText('기존 프로젝트')
      await user.click(screen.getByRole('button', { name: '새 프로젝트' }))
      const dialog = screen.getByRole('dialog', { name: '새 프로젝트' })
      await user.type(within(dialog).getByLabelText('제목'), '새로 만든 프로젝트')
      await user.click(within(dialog).getByRole('button', { name: '만들기' }))
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(await screen.findByText('새로 만든 프로젝트')).toBeInTheDocument()
      expect(screen.getByRole('heading', { level: 1, name: '대시보드' })).toBeInTheDocument()
      expect(calls()).toEqual(['GET /projects', 'POST /projects', 'GET /projects'])
    })

    it('creates from the empty-state button too', async () => {
      respondByRoute(adapter, {
        'GET /projects': (c) => reply(c, 200, []),
        'POST /projects': (c) => reply(c, 201, makeProject()),
      })
      const user = userEvent.setup()
      renderApp('/')
      await screen.findByText(/아직 프로젝트가 없습니다/)
      await user.click(screen.getAllByRole('button', { name: '새 프로젝트' })[1])
      expect(screen.getByRole('dialog', { name: '새 프로젝트' })).toBeInTheDocument()
    })

    it('does not change the list when the modal is cancelled', async () => {
      mockServer()
      const user = userEvent.setup()
      renderApp('/')
      await screen.findByText('기존 프로젝트')
      await user.click(screen.getByRole('button', { name: '새 프로젝트' }))
      await user.keyboard('{Escape}')
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(calls()).toEqual(['GET /projects'])
    })
  })
})

describe('ProjectDetail', () => {
  const project = makeProject({ id: 'p-1', title: '상세 프로젝트', description: '설명 본문' })

  it('shows a loading status first', () => {
    adapter.mockImplementation(() => new Promise(() => undefined))
    renderApp('/projects/p-1')
    expect(screen.getByRole('status')).toHaveTextContent('프로젝트를 불러오는 중')
  })

  it('shows the title, description, dates, back link and the task timeline (empty state)', async () => {
    respondByRoute(adapter, {
      'GET /projects/p-1': (c) => reply(c, 200, project),
      'GET /projects/p-1/tasks': (c) => reply(c, 200, []),
    })
    renderApp('/projects/p-1')
    expect(
      await screen.findByRole('heading', { level: 1, name: '상세 프로젝트' }),
    ).toBeInTheDocument()
    expect(screen.getByText('설명 본문')).toBeInTheDocument()
    expect(screen.getByText('생성일: 2026년 11월 1일')).toBeInTheDocument()
    expect(screen.getByText('마지막 활동: 2026년 11월 3일')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /대시보드로 돌아가기/ })).toHaveAttribute('href', '/')
    const timeline = screen.getByRole('region', { name: 'Task 타임라인' })
    expect(
      await within(timeline).findByText('아직 Task가 없습니다. 첫 Task를 만들어 보세요.'),
    ).toBeInTheDocument()
  })

  it('shows a muted placeholder when there is no description', async () => {
    respondByRoute(adapter, {
      'GET /projects/p-1': (c) => reply(c, 200, { ...project, description: null }),
    })
    renderApp('/projects/p-1')
    expect(await screen.findByText('설명이 없습니다.')).toHaveClass('text-muted-foreground')
  })

  it.each([
    [404, 'project_not_found', '요청한 프로젝트를 찾을 수 없습니다.'],
    [403, 'project_forbidden', '이 프로젝트에 접근할 권한이 없습니다.'],
  ])('shows the %i message with a link back to the dashboard', async (status, code, message) => {
    respondByRoute(adapter, {
      'GET /projects/p-1': (c) => reply(c, status, errorBody(code, message)),
    })
    renderApp('/projects/p-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('link', { name: '대시보드로 돌아가기' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: '수정' })).not.toBeInTheDocument()
  })

  it('shows other errors with a retry button', async () => {
    let attempts = 0
    respondByRoute(adapter, {
      'GET /projects/p-1': (c) => {
        attempts += 1
        return attempts === 1
          ? reply(c, 400, errorBody('bad', '일시적 오류'))
          : reply(c, 200, project)
      },
    })
    const user = userEvent.setup()
    renderApp('/projects/p-1')
    expect(await screen.findByRole('alert')).toHaveTextContent('일시적 오류')
    await user.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: '상세 프로젝트' }),
    ).toBeInTheDocument()
  })

  it('falls back to a generic message for non-API errors', async () => {
    adapter.mockRejectedValue(new Error('boom'))
    renderApp('/projects/p-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '프로젝트를 불러오지 못했습니다. 잠시 후 다시 시도하세요.',
    )
  })

  describe('edit', () => {
    function mockServer() {
      let current = project
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, current),
        'GET /projects/p-1/tasks': (c) => reply(c, 200, []),
        'GET /projects': (c) => reply(c, 200, [current]),
        'PATCH /projects/p-1': (c) => {
          current = { ...current, ...(JSON.parse(c.data as string) as object) }
          return reply(c, 200, current)
        },
      })
    }

    it('opens a dialog prefilled with the current values', async () => {
      mockServer()
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '수정' }))
      const dialog = screen.getByRole('dialog', { name: '프로젝트 수정' })
      expect(within(dialog).getByLabelText('제목')).toHaveValue('상세 프로젝트')
      expect(within(dialog).getByLabelText('설명')).toHaveValue('설명 본문')
    })

    it('persists the new values and shows them on the page', async () => {
      mockServer()
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '수정' }))
      const dialog = screen.getByRole('dialog', { name: '프로젝트 수정' })
      await user.clear(within(dialog).getByLabelText('제목'))
      await user.type(within(dialog).getByLabelText('제목'), '  바뀐 제목 ')
      await user.clear(within(dialog).getByLabelText('설명'))
      await user.click(within(dialog).getByRole('button', { name: '저장' }))
      await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
      expect(screen.getByRole('heading', { level: 1, name: '바뀐 제목' })).toBeInTheDocument()
      expect(screen.getByText('설명이 없습니다.')).toBeInTheDocument()
      const patch = adapter.mock.calls.find(([c]) => requestKey(c) === 'PATCH /projects/p-1')![0]
      expect(JSON.parse(patch.data as string)).toEqual({ title: '바뀐 제목', description: null })
    })

    it('validates the title and shows server errors in an alert', async () => {
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, project),
        'PATCH /projects/p-1': (c) =>
          reply(c, 422, errorBody('invalid_project_title', '서버 거부 메시지')),
      })
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '수정' }))
      const dialog = screen.getByRole('dialog')
      await user.clear(within(dialog).getByLabelText('제목'))
      await user.click(within(dialog).getByRole('button', { name: '저장' }))
      expect(
        within(dialog).getByText('프로젝트 제목은 최소 1자 이상이어야 합니다.'),
      ).toBeInTheDocument()
      await user.type(within(dialog).getByLabelText('제목'), 'x')
      await user.click(within(dialog).getByRole('button', { name: '저장' }))
      expect(await within(dialog).findByRole('alert')).toHaveTextContent('서버 거부 메시지')
    })

    it('cancel leaves everything unchanged', async () => {
      mockServer()
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '수정' }))
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '취소' }))
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(calls().sort()).toEqual(['GET /projects/p-1', 'GET /projects/p-1/tasks'])
    })
  })

  describe('delete', () => {
    const confirmation =
      '이 프로젝트를 삭제할까요? 프로젝트와 안의 모든 Task가 휴지통으로 이동하며 30일 동안 복구할 수 있습니다.'

    it('asks for confirmation and does not delete on cancel', async () => {
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, project),
        'GET /projects/p-1/tasks': (c) => reply(c, 200, []),
      })
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '삭제' }))
      const dialog = screen.getByRole('dialog')
      expect(dialog).toHaveTextContent(confirmation)
      await user.click(within(dialog).getByRole('button', { name: '취소' }))
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(calls().sort()).toEqual(['GET /projects/p-1', 'GET /projects/p-1/tasks'])
    })

    it('deletes and navigates to the dashboard', async () => {
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, project),
        'DELETE /projects/p-1': (c) => reply(c, 204),
        'GET /projects': (c) => reply(c, 200, []),
      })
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '삭제' }))
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '삭제' }))
      expect(await screen.findByRole('heading', { level: 1, name: '대시보드' })).toBeInTheDocument()
      expect(calls()).toContain('DELETE /projects/p-1')
      expect(calls().filter((k) => k === 'GET /projects/p-1')).toHaveLength(1)
    })

    it('shows the server error and stays when the delete fails', async () => {
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, project),
        'DELETE /projects/p-1': (c) => reply(c, 403, errorBody('project_forbidden', '권한 없음')),
      })
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '삭제' }))
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '삭제' }))
      expect(await screen.findByRole('alert')).toHaveTextContent('권한 없음')
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('forgets an earlier failure when the dialog is dismissed with Escape', async () => {
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, project),
        'DELETE /projects/p-1': (c) => reply(c, 403, errorBody('project_forbidden', '권한 없음')),
      })
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '삭제' }))
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '삭제' }))
      await screen.findByRole('alert')
      await user.keyboard('{Escape}')
      await user.click(screen.getByRole('button', { name: '삭제' }))
      expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    })

    it('disables the confirm button while the delete is running', async () => {
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, project),
        'DELETE /projects/p-1': () => new Promise(() => undefined),
      })
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '삭제' }))
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '삭제' }))
      expect(await screen.findByRole('button', { name: '삭제 중...' })).toBeDisabled()
    })

    it('uses a generic message for non-API delete failures', async () => {
      respondByRoute(adapter, {
        'GET /projects/p-1': (c) => reply(c, 200, project),
        'DELETE /projects/p-1': () => Promise.reject(new Error('boom')),
      })
      const user = userEvent.setup()
      renderApp('/projects/p-1')
      await user.click(await screen.findByRole('button', { name: '삭제' }))
      await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '삭제' }))
      expect(await screen.findByRole('alert')).toHaveTextContent(
        '프로젝트를 삭제하지 못했습니다. 잠시 후 다시 시도하세요.',
      )
    })
  })
})
