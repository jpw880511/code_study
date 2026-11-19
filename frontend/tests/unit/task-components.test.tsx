import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it } from 'vitest'

import CreateTaskModal from '../../src/components/task/CreateTaskModal'
import TaskCard from '../../src/components/task/TaskCard'
import { createQueryClient } from '../../src/lib/queryClient'
import { errorBody, mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import { makeCodeFile, makeCreateResult, makeFile, makeTask } from '../helpers/task-fixtures'

const adapter = mockApi()

describe('TaskCard', () => {
  function renderCard(task = makeTask()) {
    render(
      <MemoryRouter>
        <TaskCard task={task} />
      </MemoryRouter>,
    )
  }

  it('links to the task page and shows the number, title and description', () => {
    renderCard(makeTask({ id: 't-7', task_number: 3 }))
    expect(screen.getByRole('link')).toHaveAttribute('href', '/tasks/t-7')
    expect(screen.getByText('Task 3')).toBeInTheDocument()
    expect(screen.getByText('계산기 함수 학습')).toBeInTheDocument()
    expect(screen.getByText('덧셈과 뺄셈을 배웁니다.')).toBeInTheDocument()
  })

  it('shows language, complexity, file count, line count and the date', () => {
    renderCard()
    expect(screen.getByText(/python/)).toBeInTheDocument()
    expect(screen.getByText(/초급/)).toBeInTheDocument()
    expect(screen.getByText(/파일 1개/)).toBeInTheDocument()
    expect(screen.getByText(/120줄/)).toBeInTheDocument()
    expect(screen.getByText(/2026년 11월 16일/)).toBeInTheDocument()
  })

  it.each([
    ['intermediate', '중급'],
    ['advanced', '고급'],
  ] as const)('labels %s complexity as %s', (level, label) => {
    renderCard(makeTask({ upload: { ...makeTask().upload!, complexity_level: level } }))
    expect(screen.getByText(new RegExp(label))).toBeInTheDocument()
  })

  it('copes with a task without upload or description', () => {
    renderCard(makeTask({ upload: null, description: null }))
    expect(screen.getByText('업로드된 코드가 없습니다.')).toBeInTheDocument()
    expect(screen.queryByText('덧셈과 뺄셈을 배웁니다.')).not.toBeInTheDocument()
  })
})

function Harness({ onClose }: { onClose?: () => void }) {
  const [open, setOpen] = useState(true)
  return (
    <CreateTaskModal
      projectId="p-1"
      open={open}
      onOpenChange={(value) => {
        setOpen(value)
        if (!value) onClose?.()
      }}
    />
  )
}

function renderModal(onClose?: () => void) {
  const client = createQueryClient()
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={client}>
      <Harness onClose={onClose} />
    </QueryClientProvider>,
  )
  return { user, client }
}

function posts() {
  return adapter.mock.calls
    .map(([c]) => c)
    .filter((c) => requestKey(c) === 'POST /projects/p-1/tasks')
}

function answerCreate(result = makeCreateResult()) {
  respondByRoute(adapter, {
    'POST /projects/p-1/tasks': (c) => reply(c, 201, result),
    'GET /projects/p-1/tasks': (c) => reply(c, 200, []),
    'GET /projects/p-1': (c) => reply(c, 200, {}),
    'GET /projects': (c) => reply(c, 200, []),
  })
}

describe('CreateTaskModal', () => {
  it('renders the form with three upload method tabs, file upload first', () => {
    renderModal()
    expect(screen.getByRole('dialog', { name: '새 Task' })).toBeInTheDocument()
    expect(screen.getByLabelText('제목')).toBeInTheDocument()
    expect(screen.getByLabelText('설명')).toBeInTheDocument()
    const tabs = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(tabs).toEqual(['파일 업로드', '폴더 업로드', '코드 붙여넣기'])
    expect(screen.getByRole('tab', { name: '파일 업로드' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
    expect(screen.getByLabelText(/파일 선택/)).toBeInTheDocument()
  })

  it('switches between the three upload methods', async () => {
    const { user } = renderModal()
    await user.click(screen.getByRole('tab', { name: '폴더 업로드' }))
    expect(screen.getByLabelText(/폴더 선택/)).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    expect(screen.getByLabelText('프로그래밍 언어')).toBeInTheDocument()
  })

  it('validates the title and description in the browser without calling the server', async () => {
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '짧음')
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    expect(screen.getByText('Task 제목은 최소 5자 이상이어야 합니다.')).toBeInTheDocument()
    expect(screen.getByText('업로드할 파일을 선택하세요.')).toBeInTheDocument()
    expect(adapter).not.toHaveBeenCalled()
  })

  it('shows an unsupported file immediately and blocks the submit', async () => {
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('virus.exe'))
    expect(screen.getByRole('alert')).toHaveTextContent('지원하지 않는 파일 형식입니다 (.exe)')
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    expect(adapter).not.toHaveBeenCalled()
  })

  it('rejects more than 20 files right away', async () => {
    const { user } = renderModal()
    await user.upload(
      screen.getByLabelText(/파일 선택/),
      Array.from({ length: 21 }, (_, i) => makeFile(`f${i}.py`)),
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      '업로드당 최대 20개 파일까지 가능합니다. 파일 수를 줄이거나 폴더 업로드를 사용하세요.',
    )
  })

  it('requires a language for pasted code', async () => {
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    await user.type(screen.getByLabelText('코드'), 'print(1)')
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    expect(screen.getByRole('alert')).toHaveTextContent(
      '업로드하기 전에 프로그래밍 언어를 선택하세요.',
    )
    expect(adapter).not.toHaveBeenCalled()
  })

  it('uploads files, then shows the confirmation with the file list', async () => {
    answerCreate(
      makeCreateResult({
        files: [
          makeCodeFile({
            id: 'f-1',
            file_name: 'a.py',
            file_path: 'src/a.py',
            file_size_bytes: 100,
          }),
          makeCodeFile({ id: 'f-2', file_name: 'b.py', file_path: null, file_size_bytes: 2048 }),
        ],
      }),
    )
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.type(screen.getByLabelText('설명'), '설명입니다')
    await user.upload(screen.getByLabelText(/파일 선택/), [makeFile('a.py'), makeFile('b.py')])
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))

    const dialog = await screen.findByRole('dialog', { name: '업로드 확인' })
    expect(posts()).toHaveLength(1)
    const form = posts()[0].data as FormData
    expect(form.get('title')).toBe('정상적인 제목')
    expect(form.get('description')).toBe('설명입니다')
    expect(form.getAll('files')).toHaveLength(2)
    const list = within(dialog).getByRole('list', { name: '업로드된 파일' })
    expect(within(list).getByText('src/a.py')).toBeInTheDocument()
    expect(within(list).getByText('b.py')).toBeInTheDocument()
    expect(within(dialog).getByText(/Task 1/)).toBeInTheDocument()
  })

  it('invalidates the task list on success and closes on 확인', async () => {
    answerCreate()
    let closed = 0
    const { user, client } = renderModal(() => closed++)
    client.setQueryData(['projects', 'p-1', 'tasks'], [])
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('a.py'))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    await screen.findByRole('dialog', { name: '업로드 확인' })
    expect(client.getQueryState(['projects', 'p-1', 'tasks'])?.isInvalidated).toBe(true)
    await user.click(screen.getByRole('button', { name: '확인' }))
    expect(closed).toBe(1)
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('sends folder uploads with relative paths and mentions what was excluded', async () => {
    answerCreate(makeCreateResult({ excluded_paths: ['x/.git/config'] }))
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.click(screen.getByRole('tab', { name: '폴더 업로드' }))
    await user.upload(screen.getByLabelText(/폴더 선택/), [
      makeFile('App.jsx', 'x', 'my-app/src/App.jsx'),
      makeFile('index.js', 'x', 'my-app/node_modules/a/index.js'),
    ])
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    const dialog = await screen.findByRole('dialog', { name: '업로드 확인' })
    const form = posts()[0].data as FormData
    expect(form.get('upload_method')).toBe('folder')
    expect(form.getAll('paths')).toEqual(['my-app/src/App.jsx'])
    expect(form.getAll('files')).toHaveLength(1)
    expect(dialog).toHaveTextContent(
      '일반적인 빌드/시스템 폴더를 제외했습니다: .git, node_modules, __pycache__',
    )
    expect(dialog).toHaveTextContent('제외된 파일 2개')
  })

  it('sends pasted code with its language', async () => {
    answerCreate()
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    await user.type(screen.getByLabelText('코드'), 'print(1)')
    await user.selectOptions(screen.getByLabelText('프로그래밍 언어'), 'python')
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    await screen.findByRole('dialog', { name: '업로드 확인' })
    const form = posts()[0].data as FormData
    expect(form.get('upload_method')).toBe('paste')
    expect(form.get('code')).toBe('print(1)')
    expect(form.get('language')).toBe('python')
  })

  it('keeps what was typed when switching tabs', async () => {
    const { user } = renderModal()
    await user.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    await user.type(screen.getByLabelText('코드'), 'abc')
    await user.click(screen.getByRole('tab', { name: '파일 업로드' }))
    await user.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    expect(screen.getByLabelText('코드')).toHaveValue('abc')
  })

  it('shows the large-code warning from the server', async () => {
    const message =
      '큰 코드 파일이 감지되었습니다. 500줄을 넘는 코드는 문서 생성에 3~5분이 걸릴 수 있습니다.'
    answerCreate(makeCreateResult({ warnings: [{ code: 'large_code', message }] }))
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('a.py'))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    expect(await screen.findByText(message)).toBeInTheDocument()
  })

  it('shows the server error with its suggestion and stays open', async () => {
    respondByRoute(adapter, {
      'POST /projects/p-1/tasks': (c) =>
        reply(c, 415, {
          ...errorBody('binary_file_rejected', '바이너리 파일은 업로드할 수 없습니다.'),
          suggestion: '텍스트 형식의 소스 코드 파일만 업로드하세요.',
        }),
    })
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('a.py'))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('바이너리 파일은 업로드할 수 없습니다.')
    expect(alert).toHaveTextContent('텍스트 형식의 소스 코드 파일만 업로드하세요.')
    expect(screen.getByRole('dialog', { name: '새 Task' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Task 만들기' })).toBeEnabled()
  })

  it('drops an earlier server error when a later submit fails the browser check', async () => {
    respondByRoute(adapter, {
      'POST /projects/p-1/tasks': (c) =>
        reply(c, 415, {
          ...errorBody('binary_file_rejected', '바이너리 파일은 업로드할 수 없습니다.'),
          suggestion: '텍스트 형식의 소스 코드 파일만 업로드하세요.',
        }),
    })
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('a.py'))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    expect(await screen.findByText('바이너리 파일은 업로드할 수 없습니다.')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: '코드 붙여넣기' }))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))

    expect(screen.getByText('업로드하기 전에 프로그래밍 언어를 선택하세요.')).toBeInTheDocument()
    expect(screen.queryByText('바이너리 파일은 업로드할 수 없습니다.')).not.toBeInTheDocument()
    expect(
      screen.queryByText('텍스트 형식의 소스 코드 파일만 업로드하세요.'),
    ).not.toBeInTheDocument()
    expect(screen.getAllByRole('alert')).toHaveLength(1)
  })

  it('falls back to a generic message without a server answer', async () => {
    adapter.mockImplementation(async () => {
      throw new Error('boom')
    })
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('a.py'))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Task를 만들지 못했습니다. 잠시 후 다시 시도하세요.',
    )
  })

  it('disables the button while uploading and cancels without a request', async () => {
    adapter.mockImplementation(() => new Promise(() => undefined))
    const { user } = renderModal()
    await user.type(screen.getByLabelText('제목'), '정상적인 제목')
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('a.py'))
    await user.click(screen.getByRole('button', { name: 'Task 만들기' }))
    expect(await screen.findByRole('button', { name: '업로드하는 중...' })).toBeDisabled()
  })

  it('closes on 취소', async () => {
    let closed = 0
    const { user } = renderModal(() => closed++)
    await user.click(screen.getByRole('button', { name: '취소' }))
    expect(closed).toBe(1)
    expect(adapter).not.toHaveBeenCalled()
  })
})
