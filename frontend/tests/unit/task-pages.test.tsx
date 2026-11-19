import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { createQueryClient } from '../../src/lib/queryClient'
import ProjectDetail from '../../src/pages/ProjectDetail'
import TaskDetail from '../../src/pages/TaskDetail'
import { useAuthStore } from '../../src/stores/auth-store'
import { errorBody, mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import { makeProject } from '../helpers/project-fixtures'
import {
  makeCodeFile,
  makeCreateResult,
  makeFile,
  makeTask,
  makeTaskDetail,
} from '../helpers/task-fixtures'

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
          <Route path="/" element={<p>대시보드 화면</p>} />
          <Route path="/projects/:projectId" element={<ProjectDetail />} />
          <Route path="/tasks/:taskId" element={<TaskDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const calls = () => adapter.mock.calls.map(([c]) => requestKey(c))

describe('ProjectDetail task section', () => {
  const project = makeProject({ id: 'p-1' })

  function answer(tasks: ReturnType<typeof makeTask>[] | 'error' | 'pending') {
    respondByRoute(adapter, {
      'GET /projects/p-1': (c) => reply(c, 200, project),
      'GET /projects/p-1/tasks': (c) => {
        if (tasks === 'pending') return new Promise(() => undefined)
        if (tasks === 'error') return reply(c, 500, errorBody('server_error', '서버 오류입니다.'))
        return reply(c, 200, tasks)
      },
    })
  }

  it('shows a loading status while the tasks load', async () => {
    answer('pending')
    renderApp('/projects/p-1')
    const region = await screen.findByRole('region', { name: 'Task 타임라인' })
    expect(within(region).getByRole('status')).toHaveTextContent('Task를 불러오는 중')
  })

  it('shows the empty state and a "새 Task" button', async () => {
    answer([])
    renderApp('/projects/p-1')
    expect(
      await screen.findByText('아직 Task가 없습니다. 첫 Task를 만들어 보세요.'),
    ).toBeInTheDocument()
    expect(screen.getByRole('button', { name: '새 Task' })).toBeInTheDocument()
  })

  it('lists the tasks in the order the server sent them and links to /tasks/:id', async () => {
    answer([
      makeTask({ id: 'a', task_number: 1, title: '첫 번째 Task' }),
      makeTask({ id: 'b', task_number: 2, title: '두 번째 Task' }),
      makeTask({ id: 'c', task_number: 3, title: '세 번째 Task' }),
    ])
    renderApp('/projects/p-1')
    const list = await screen.findByRole('list', { name: 'Task 목록' })
    const links = within(list).getAllByRole('link')
    expect(links.map((l) => l.getAttribute('href'))).toEqual(['/tasks/a', '/tasks/b', '/tasks/c'])
    expect(links.map((l) => l.textContent)).toEqual([
      expect.stringContaining('Task 1'),
      expect.stringContaining('Task 2'),
      expect.stringContaining('Task 3'),
    ])
    expect(screen.queryByText(/아직 Task가 없습니다/)).not.toBeInTheDocument()
  })

  it('navigates to the task page when a card is clicked', async () => {
    const user = userEvent.setup()
    answer([makeTask({ id: 'a', title: '클릭할 Task' })])
    respondByRoute(adapter, {
      'GET /projects/p-1': (c) => reply(c, 200, project),
      'GET /projects/p-1/tasks': (c) =>
        reply(c, 200, [makeTask({ id: 'a', title: '클릭할 Task' })]),
      'GET /tasks/a': (c) => reply(c, 200, makeTaskDetail({ id: 'a', title: '클릭할 Task' })),
    })
    renderApp('/projects/p-1')
    await user.click(await screen.findByRole('link', { name: /클릭할 Task/ }))
    expect(
      await screen.findByRole('heading', { level: 1, name: '클릭할 Task' }),
    ).toBeInTheDocument()
  })

  it('shows the error with a retry button', async () => {
    const user = userEvent.setup()
    answer('error')
    renderApp('/projects/p-1')
    const region = await screen.findByRole('region', { name: 'Task 타임라인' })
    expect(await within(region).findByRole('alert')).toHaveTextContent('서버 오류입니다.')
    const before = calls().filter((c) => c === 'GET /projects/p-1/tasks').length
    await user.click(within(region).getByRole('button', { name: '다시 시도' }))
    await screen.findByRole('alert')
    expect(calls().filter((c) => c === 'GET /projects/p-1/tasks').length).toBeGreaterThan(before)
  })

  it('creates a task through the modal and shows it in the list', async () => {
    const user = userEvent.setup()
    let created = false
    respondByRoute(adapter, {
      'GET /projects/p-1': (c) => reply(c, 200, project),
      'GET /projects': (c) => reply(c, 200, [project]),
      'GET /projects/p-1/tasks': (c) =>
        reply(c, 200, created ? [makeTask({ id: 'n', title: '새로 만든 Task' })] : []),
      'POST /projects/p-1/tasks': (c) => {
        created = true
        return reply(c, 201, makeCreateResult({ title: '새로 만든 Task' }))
      },
    })
    renderApp('/projects/p-1')
    await user.click(await screen.findByRole('button', { name: '새 Task' }))
    await user.type(screen.getByLabelText('제목'), '새로 만든 Task')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('calc.py'))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    await user.click(await screen.findByRole('button', { name: '확인' }))
    expect(await screen.findByRole('link', { name: /새로 만든 Task/ })).toBeInTheDocument()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})

describe('TaskDetail', () => {
  const detail = makeTaskDetail({
    id: 't-1',
    project_id: 'p-1',
    task_number: 4,
    title: '상세 Task 제목',
    description: '상세 설명입니다.',
    files: [
      makeCodeFile({
        id: 'f-1',
        file_name: 'App.jsx',
        file_path: 'src/App.jsx',
        file_size_bytes: 2048,
      }),
      makeCodeFile({ id: 'f-2', file_name: 'main.py', file_path: null, file_size_bytes: 10 }),
    ],
    upload: {
      detected_language: 'javascript',
      complexity_level: 'advanced',
      total_lines: 300,
      total_files: 2,
      upload_size_bytes: 2058,
    },
  })

  it('shows a loading status first', () => {
    adapter.mockImplementation(() => new Promise(() => undefined))
    renderApp('/tasks/t-1')
    expect(screen.getByRole('status')).toHaveTextContent('Task를 불러오는 중')
  })

  it('shows the header, language, complexity and the uploaded files', async () => {
    respondByRoute(adapter, { 'GET /tasks/t-1': (c) => reply(c, 200, detail) })
    renderApp('/tasks/t-1')
    expect(
      await screen.findByRole('heading', { level: 1, name: '상세 Task 제목' }),
    ).toBeInTheDocument()
    expect(screen.getByText('Task 4')).toBeInTheDocument()
    expect(screen.getByText('상세 설명입니다.')).toBeInTheDocument()
    expect(screen.getByText('언어: javascript')).toBeInTheDocument()
    expect(screen.getByText('복잡도: 고급')).toBeInTheDocument()
    const files = screen.getByRole('list', { name: '업로드된 파일' })
    expect(
      within(files)
        .getAllByRole('listitem')
        .map((i) => i.textContent),
    ).toEqual([expect.stringContaining('src/App.jsx'), expect.stringContaining('main.py')])
    expect(screen.getByRole('link', { name: /프로젝트로 돌아가기/ })).toHaveAttribute(
      'href',
      '/projects/p-1',
    )
  })

  it('handles a task without description or uploaded code', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1': (c) =>
        reply(c, 200, makeTaskDetail({ description: null, upload: null, files: [] })),
    })
    renderApp('/tasks/t-1')
    expect(await screen.findByText('설명이 없습니다.')).toBeInTheDocument()
    expect(screen.getByText('업로드된 코드가 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('list', { name: '업로드된 파일' })).not.toBeInTheDocument()
  })

  it('has the three tabs: the document tab shows the document, the others are "준비 중" placeholders', async () => {
    const user = userEvent.setup()
    respondByRoute(adapter, {
      'GET /tasks/t-1': (c) => reply(c, 200, detail),
      'GET /tasks/t-1/document/status': (c) => reply(c, 404, errorBody('document_not_found')),
    })
    renderApp('/tasks/t-1')
    await screen.findByRole('heading', { level: 1 })
    expect(screen.getAllByRole('tab').map((t) => t.textContent)).toEqual([
      '문서',
      '연습문제',
      'Q&A',
    ])
    expect(await screen.findByText('아직 학습 문서가 없습니다.')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '연습문제' }))
    expect(screen.getByRole('tabpanel')).toHaveTextContent('연습문제 기능은 준비 중입니다.')
    await user.click(screen.getByRole('tab', { name: 'Q&A' }))
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Q&A 기능은 준비 중입니다.')
  })

  it('uses a wide page only while the document tab is open', async () => {
    const user = userEvent.setup()
    respondByRoute(adapter, {
      'GET /tasks/t-1': (c) => reply(c, 200, detail),
      'GET /tasks/t-1/document/status': (c) => reply(c, 404, errorBody('document_not_found')),
    })
    renderApp('/tasks/t-1')
    const page = (await screen.findByRole('heading', { level: 1 })).closest('article')
    expect(page).toHaveClass('max-w-7xl')
    await user.click(screen.getByRole('tab', { name: '연습문제' }))
    expect(page).toHaveClass('max-w-3xl')
    expect(page).not.toHaveClass('max-w-7xl')
    await user.click(screen.getByRole('tab', { name: '문서' }))
    expect(page).toHaveClass('max-w-7xl')
  })

  it('shows the document progress for the task in the document tab', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1': (c) => reply(c, 200, detail),
      'GET /tasks/t-1/document/status': (c) =>
        reply(c, 200, {
          status: 'in_progress',
          generation_started_at: null,
          generation_completed_at: null,
          elapsed_seconds: 2,
          estimated_total_seconds: 20,
          notice: null,
          error: null,
        }),
    })
    renderApp('/tasks/t-1')
    expect(await screen.findByRole('progressbar', { name: '문서 생성 진행률' })).toBeInTheDocument()
    expect(screen.getByText('약 18초 남음')).toBeInTheDocument()
  })

  it.each([
    [404, 'task_not_found', '요청한 Task를 찾을 수 없습니다.'],
    [403, 'task_forbidden', '이 Task에 접근할 권한이 없습니다.'],
  ])('shows the %i message with only a way back', async (status, code, message) => {
    respondByRoute(adapter, { 'GET /tasks/t-1': (c) => reply(c, status, errorBody(code, message)) })
    renderApp('/tasks/t-1')
    expect(await screen.findByRole('alert')).toHaveTextContent(message)
    expect(screen.getByRole('link', { name: '대시보드로 돌아가기' })).toHaveAttribute('href', '/')
    expect(screen.queryByRole('button', { name: '다시 시도' })).not.toBeInTheDocument()
  })

  it('offers a retry for other errors', async () => {
    const user = userEvent.setup()
    let fail = true
    respondByRoute(adapter, {
      'GET /tasks/t-1': (c) =>
        fail ? reply(c, 500, errorBody('server_error', '서버 오류입니다.')) : reply(c, 200, detail),
    })
    renderApp('/tasks/t-1')
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류입니다.')
    fail = false
    await user.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(
      await screen.findByRole('heading', { level: 1, name: '상세 Task 제목' }),
    ).toBeInTheDocument()
  })
})
