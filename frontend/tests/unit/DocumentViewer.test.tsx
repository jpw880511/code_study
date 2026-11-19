import { QueryClientProvider } from '@tanstack/react-query'
import { act, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'

import DocumentViewer from '../../src/components/document/DocumentViewer'
import { createQueryClient } from '../../src/lib/queryClient'
import { errorBody, mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import {
  makeContent,
  makeDocument,
  makeStatus,
  makeTaskCode,
  makeTaskCodeFile,
} from '../helpers/document-fixtures'

vi.mock('../../src/components/document/CodeEditor', () => import('../helpers/fake-code-editor'))

const adapter = mockApi()

afterEach(() => {
  vi.useRealTimers()
})

function renderViewer() {
  const client = createQueryClient()
  client.setDefaultOptions({
    ...client.getDefaultOptions(),
    queries: { ...client.getDefaultOptions().queries, retry: false },
  })
  return render(
    <QueryClientProvider client={client}>
      <DocumentViewer taskId="t-1" />
    </QueryClientProvider>,
  )
}

const calls = () => adapter.mock.calls.map(([c]) => requestKey(c))

function answerCompleted(content = makeContent(), code = makeTaskCode()) {
  respondByRoute(adapter, {
    'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus()),
    'GET /tasks/t-1/document': (c) => reply(c, 200, makeDocument({ content })),
    'GET /tasks/t-1/code': (c) => reply(c, 200, code),
  })
}

async function openChapter4(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('button', { name: /^4장/ }))
}

describe('DocumentViewer states', () => {
  it('shows a status while the document state loads', () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': () => new Promise(() => undefined),
    })
    renderViewer()
    expect(screen.getByRole('status')).toHaveTextContent('문서 상태를 확인하는 중')
  })

  it('says there is no document when the server answers document_not_found', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 404, errorBody('document_not_found')),
    })
    renderViewer()
    expect(await screen.findByText('아직 학습 문서가 없습니다.')).toBeInTheDocument()
    expect(calls()).toEqual(['GET /tasks/t-1/document/status'])
  })

  it('waits while pending without loading the document or the code', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) =>
        reply(c, 200, makeStatus({ status: 'pending', estimated_total_seconds: 20 })),
    })
    renderViewer()
    expect(await screen.findByText('문서 생성을 기다리는 중')).toBeInTheDocument()
    expect(calls()).toEqual(['GET /tasks/t-1/document/status'])
  })

  it('shows progress while in progress and then the document once it completes', async () => {
    vi.useFakeTimers()
    let status = makeStatus({
      status: 'in_progress',
      elapsed_seconds: 4,
      estimated_total_seconds: 20,
    })
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, status),
      'GET /tasks/t-1/document': (c) => reply(c, 200, makeDocument()),
      'GET /tasks/t-1/code': (c) => reply(c, 200, makeTaskCode()),
    })
    renderViewer()
    await act(() => vi.advanceTimersByTimeAsync(0))
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '20')
    expect(screen.getByText('약 16초 남음')).toBeInTheDocument()
    status = makeStatus({ status: 'in_progress', elapsed_seconds: 6, estimated_total_seconds: 20 })
    await act(() => vi.advanceTimersByTimeAsync(2100))
    expect(screen.getByText('약 14초 남음')).toBeInTheDocument()
    status = makeStatus()
    await act(() => vi.advanceTimersByTimeAsync(2100))
    await act(() => vi.advanceTimersByTimeAsync(0))
    expect(screen.getByRole('navigation', { name: '챕터 탐색' })).toBeInTheDocument()
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
    const before = calls().length
    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(calls()).toHaveLength(before)
  })

  it('stops polling when the viewer goes away', async () => {
    vi.useFakeTimers()
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus({ status: 'pending' })),
    })
    const { unmount } = renderViewer()
    await act(() => vi.advanceTimersByTimeAsync(0))
    unmount()
    const before = calls().length
    await act(() => vi.advanceTimersByTimeAsync(10_000))
    expect(calls()).toHaveLength(before)
  })

  it('shows the failure text as an alert and offers no restart', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) =>
        reply(
          c,
          200,
          makeStatus({ status: 'failed', error: '문서를 만들지 못했습니다. 다시 확인하세요.' }),
        ),
    })
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '문서를 만들지 못했습니다. 다시 확인하세요.',
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('shows an alert with a retry button when the status cannot be loaded', async () => {
    const user = userEvent.setup()
    let fail = true
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) =>
        fail
          ? reply(c, 500, errorBody('server_error', '서버 오류입니다.'))
          : reply(c, 200, makeStatus({ status: 'pending' })),
    })
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent('서버 오류입니다.')
    fail = false
    await user.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(await screen.findByText('문서 생성을 기다리는 중')).toBeInTheDocument()
  })

  it('shows a loading status while a completed document and its code load', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus()),
      'GET /tasks/t-1/document': () => new Promise(() => undefined),
      'GET /tasks/t-1/code': () => new Promise(() => undefined),
    })
    renderViewer()
    expect(await screen.findByText('학습 문서를 불러오는 중...')).toBeInTheDocument()
  })

  it('shows an alert with retry when the completed document cannot be loaded', async () => {
    const user = userEvent.setup()
    let fail = true
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus()),
      'GET /tasks/t-1/document': (c) =>
        fail
          ? reply(c, 500, errorBody('server_error', '문서 서버 오류입니다.'))
          : reply(c, 200, makeDocument()),
      'GET /tasks/t-1/code': (c) => reply(c, 200, makeTaskCode()),
    })
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent('문서 서버 오류입니다.')
    fail = false
    await user.click(screen.getByRole('button', { name: '다시 시도' }))
    expect(await screen.findByRole('navigation', { name: '챕터 탐색' })).toBeInTheDocument()
  })

  it('shows an alert with retry when the code cannot be loaded', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus()),
      'GET /tasks/t-1/document': (c) => reply(c, 200, makeDocument()),
      'GET /tasks/t-1/code': (c) =>
        reply(c, 500, errorBody('server_error', '코드 서버 오류입니다.')),
    })
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent('코드 서버 오류입니다.')
    expect(screen.getByRole('button', { name: '다시 시도' })).toBeInTheDocument()
  })

  it('shows an alert when a completed document has no content', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus()),
      'GET /tasks/t-1/document': (c) => reply(c, 200, makeDocument({ content: null })),
      'GET /tasks/t-1/code': (c) => reply(c, 200, makeTaskCode()),
    })
    renderViewer()
    expect(await screen.findByRole('alert')).toHaveTextContent(
      '학습 문서의 내용을 불러오지 못했습니다.',
    )
  })
})

describe('DocumentViewer reading', () => {
  it('puts the code and the explanation side by side on wide screens and stacked on narrow ones', async () => {
    answerCompleted()
    renderViewer()
    const viewer = await screen.findByRole('region', { name: '학습 문서' })
    expect(viewer.className).toContain('lg:grid-cols-2')
    expect(viewer.className).toContain('grid-cols-1')
    expect(within(viewer).getByTestId('code-editor')).toBeInTheDocument()
    expect(within(viewer).getByRole('navigation', { name: '챕터 탐색' })).toBeInTheDocument()
  })

  it('shows the code with the detected language', async () => {
    answerCompleted()
    renderViewer()
    const editor = await screen.findByTestId('code-editor')
    expect(editor).toHaveAttribute('data-language', 'python')
    expect(editor).toHaveTextContent('def add(a, b):')
  })

  it('highlights the lines of the chosen chapter 4 entry in the code panel', async () => {
    const user = userEvent.setup()
    answerCompleted()
    renderViewer()
    await openChapter4(user)
    expect(screen.getByTestId('code-editor')).toHaveAttribute('data-highlight', '')
    await user.click(screen.getByText('결과를 화면에 출력합니다.'))
    expect(screen.getByTestId('code-editor').getAttribute('data-highlight')).toMatch(/^4-5#/)
    expect(screen.getByRole('button', { name: 'calc.py 4~5줄 코드에서 보기' })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('highlights on keyboard focus too', async () => {
    const user = userEvent.setup()
    answerCompleted()
    renderViewer()
    await openChapter4(user)
    act(() => screen.getByRole('button', { name: 'calc.py 1~2줄 코드에서 보기' }).focus())
    expect(screen.getByTestId('code-editor').getAttribute('data-highlight')).toMatch(/^1-2#/)
  })

  it('follows the code scroll: the entry that contains the first visible line becomes current', async () => {
    const user = userEvent.setup()
    answerCompleted()
    renderViewer()
    await openChapter4(user)
    await user.click(screen.getByRole('button', { name: '4줄로 스크롤' }))
    expect(screen.getByRole('button', { name: 'calc.py 4~5줄 코드에서 보기' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    await user.click(screen.getByRole('button', { name: '2줄로 스크롤' }))
    expect(screen.getByRole('button', { name: 'calc.py 1~2줄 코드에서 보기' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('button', { name: 'calc.py 4~5줄 코드에서 보기' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('keeps the current entry over lines that no entry explains', async () => {
    const user = userEvent.setup()
    answerCompleted()
    renderViewer()
    await openChapter4(user)
    await user.click(screen.getByRole('button', { name: '1줄로 스크롤' }))
    await user.click(screen.getByRole('button', { name: '3줄로 스크롤' }))
    expect(screen.getByRole('button', { name: 'calc.py 1~2줄 코드에서 보기' })).toHaveAttribute(
      'aria-current',
      'true',
    )
  })

  it('works when chapter 4 has no entries', async () => {
    const user = userEvent.setup()
    const base = makeContent()
    answerCompleted(makeContent({ chapter4: { ...base.chapter4, explanations: [] } }))
    renderViewer()
    await openChapter4(user)
    await user.click(screen.getByRole('button', { name: '2줄로 스크롤' }))
    expect(screen.getByText('줄별 설명이 없습니다.')).toBeInTheDocument()
  })

  it('does not feed back: scrolling the code never asks the code panel to highlight or scroll', async () => {
    const user = userEvent.setup()
    answerCompleted()
    renderViewer()
    await openChapter4(user)
    await user.click(screen.getByText('결과를 화면에 출력합니다.'))
    const highlight = screen.getByTestId('code-editor').getAttribute('data-highlight')
    await user.click(screen.getByRole('button', { name: '1줄로 스크롤' }))
    await user.click(screen.getByRole('button', { name: '4줄로 스크롤' }))
    expect(screen.getByTestId('code-editor').getAttribute('data-highlight')).toBe(highlight)
  })

  it('scrolls the explanation into view only when the code panel moved it', async () => {
    const user = userEvent.setup()
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    answerCompleted()
    renderViewer()
    await openChapter4(user)
    await user.click(screen.getByText('결과를 화면에 출력합니다.'))
    expect(scrollIntoView).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: '1줄로 스크롤' }))
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    // The same entry again (line 2 is still in entry 1) causes no further movement.
    await user.click(screen.getByRole('button', { name: '2줄로 스크롤' }))
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    // @ts-expect-error cleanup of the jsdom gap filled above
    delete Element.prototype.scrollIntoView
  })

  it("follows the file too: a scroll in the second file selects that file's entry", async () => {
    const user = userEvent.setup()
    const base = makeContent()
    const entry = base.chapter4.explanations[0]
    const content = makeContent({
      chapter4: {
        title: '한 줄씩 설명',
        explanations: [
          entry,
          {
            ...entry,
            file: 'src/util.py',
            line_start: 1,
            line_end: 3,
            what_it_does: '도구 함수입니다.',
          },
        ],
      },
    })
    const code = makeTaskCode([
      makeTaskCodeFile({ id: 'f-1' }),
      makeTaskCodeFile({ id: 'f-2', file_name: 'util.py', file_path: 'src/util.py', content: 'x' }),
    ])
    answerCompleted(content, code)
    renderViewer()
    await openChapter4(user)
    await user.click(screen.getByRole('tab', { name: 'src/util.py' }))
    expect(screen.getByRole('button', { name: 'src/util.py 1~3줄 코드에서 보기' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    await user.click(screen.getByText('도구 함수입니다.'))
    expect(screen.getByTestId('code-editor').getAttribute('data-highlight')).toMatch(/^1-3#/)
    expect(screen.getByRole('tab', { name: 'src/util.py' })).toHaveAttribute(
      'aria-selected',
      'true',
    )
  })

  it('shows document text as plain text', async () => {
    const base = makeContent()
    answerCompleted(
      makeContent({ chapter1: { ...base.chapter1, summary: '<div id="boom">a < b</div>' } }),
    )
    renderViewer()
    await waitFor(() => expect(screen.getByText('<div id="boom">a < b</div>')).toBeInTheDocument())
    expect(document.getElementById('boom')).toBeNull()
  })
})
