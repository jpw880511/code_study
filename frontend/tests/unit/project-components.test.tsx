import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { describe, expect, it, vi } from 'vitest'

import CreateProjectModal from '../../src/components/project/CreateProjectModal'
import ProjectCard from '../../src/components/project/ProjectCard'
import { createQueryClient } from '../../src/lib/queryClient'
import { errorBody, mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import { makeProject } from '../helpers/project-fixtures'

const adapter = mockApi()

describe('ProjectCard', () => {
  function renderCard(project = makeProject()) {
    return render(
      <MemoryRouter>
        <ProjectCard project={project} />
      </MemoryRouter>,
    )
  }

  it('shows the title, the description and the formatted last activity', () => {
    renderCard()
    expect(screen.getByText('알고리즘 스터디')).toBeInTheDocument()
    expect(screen.getByText('정렬 알고리즘을 분석합니다.')).toBeInTheDocument()
    expect(screen.getByText('마지막 활동: 2026년 11월 3일')).toBeInTheDocument()
  })

  it('links the whole card to the project page, named after the title', () => {
    renderCard(makeProject({ id: 'abc' }))
    const link = screen.getByRole('link', { name: /알고리즘 스터디/ })
    expect(link).toHaveAttribute('href', '/projects/abc')
    expect(link).toHaveTextContent('마지막 활동')
  })

  it('shows no description element when it is null', () => {
    renderCard(makeProject({ description: null }))
    expect(screen.queryByTestId('project-card-description')).not.toBeInTheDocument()
  })

  it('clamps a long description', () => {
    renderCard()
    expect(screen.getByTestId('project-card-description')).toHaveClass('line-clamp-3')
  })
})

describe('CreateProjectModal', () => {
  function renderModal(onOpenChange = vi.fn(), open = true) {
    const view = render(
      <QueryClientProvider client={createQueryClient()}>
        <CreateProjectModal open={open} onOpenChange={onOpenChange} />
      </QueryClientProvider>,
    )
    return { onOpenChange, ...view }
  }

  const submit = () => screen.getByRole('button', { name: '만들기' })

  it('renders nothing when closed', () => {
    renderModal(vi.fn(), false)
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })

  it('has a titled dialog with labelled fields', () => {
    renderModal()
    expect(screen.getByRole('dialog', { name: '새 프로젝트' })).toBeInTheDocument()
    expect(screen.getByLabelText('제목')).toBeRequired()
    expect(screen.getByLabelText('설명')).not.toBeRequired()
  })

  it('rejects an empty or blank title without calling the server', async () => {
    const user = userEvent.setup()
    renderModal()
    await user.click(submit())
    expect(screen.getByText('프로젝트 제목은 최소 1자 이상이어야 합니다.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('제목'), '   ')
    await user.click(submit())
    expect(screen.getByText('프로젝트 제목은 최소 1자 이상이어야 합니다.')).toBeInTheDocument()
    expect(adapter).not.toHaveBeenCalled()
  })

  it('rejects a title over 255 characters', async () => {
    const user = userEvent.setup()
    renderModal()
    await user.click(screen.getByLabelText('제목'))
    await user.paste('a'.repeat(256))
    await user.click(submit())
    expect(screen.getByText('프로젝트 제목은 최대 255자까지 입력 가능합니다.')).toBeInTheDocument()
    expect(adapter).not.toHaveBeenCalled()
  })

  it('shows the remaining description characters and rejects an overlong one', async () => {
    const user = userEvent.setup()
    renderModal()
    expect(screen.getByText('2000자 남음')).toBeInTheDocument()
    await user.click(screen.getByLabelText('설명'))
    await user.paste('a'.repeat(5))
    expect(screen.getByText('1995자 남음')).toBeInTheDocument()
    await user.paste('a'.repeat(2000))
    expect(screen.getByText('-5자 남음')).toBeInTheDocument()
    await user.type(screen.getByLabelText('제목'), 'T')
    await user.click(submit())
    expect(screen.getByText('프로젝트 설명은 최대 2000자까지 입력 가능합니다.')).toBeInTheDocument()
    expect(adapter).not.toHaveBeenCalled()
  })

  it('posts the trimmed values and closes on success', async () => {
    respondByRoute(adapter, {
      'POST /projects': (c) => reply(c, 201, makeProject()),
      'GET /projects': (c) => reply(c, 200, []),
    })
    const user = userEvent.setup()
    const { onOpenChange } = renderModal()
    await user.type(screen.getByLabelText('제목'), '  새 제목  ')
    await user.type(screen.getByLabelText('설명'), '  설명  ')
    await user.click(submit())
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    const post = adapter.mock.calls.find(([c]) => requestKey(c) === 'POST /projects')![0]
    expect(JSON.parse(post.data as string)).toEqual({ title: '새 제목', description: '설명' })
  })

  it('omits an empty description', async () => {
    respondByRoute(adapter, { 'POST /projects': (c) => reply(c, 201, makeProject()) })
    const user = userEvent.setup()
    const { onOpenChange } = renderModal()
    await user.type(screen.getByLabelText('제목'), 'T')
    await user.click(submit())
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
    expect(JSON.parse(adapter.mock.calls[0][0].data as string)).toEqual({ title: 'T' })
  })

  it('disables the submit while pending and sends only one request on a double click', async () => {
    let release: () => void = () => undefined
    const gate = new Promise<void>((resolve) => (release = resolve))
    respondByRoute(adapter, {
      'POST /projects': async (c) => {
        await gate
        return reply(c, 201, makeProject())
      },
    })
    const user = userEvent.setup()
    const { onOpenChange } = renderModal()
    await user.type(screen.getByLabelText('제목'), 'T')
    await user.dblClick(submit())
    expect(screen.getByRole('button', { name: '만드는 중...' })).toBeDisabled()
    expect(adapter).toHaveBeenCalledTimes(1)
    release()
    await waitFor(() => expect(onOpenChange).toHaveBeenCalledWith(false))
  })

  it('shows the server error in an alert and stays open', async () => {
    respondByRoute(adapter, {
      'POST /projects': (c) =>
        reply(c, 422, errorBody('invalid_project_title', '서버가 거부한 제목입니다.')),
    })
    const user = userEvent.setup()
    const { onOpenChange } = renderModal()
    await user.type(screen.getByLabelText('제목'), 'T')
    await user.click(submit())
    expect(await screen.findByRole('alert')).toHaveTextContent('서버가 거부한 제목입니다.')
    expect(onOpenChange).not.toHaveBeenCalled()
    expect(submit()).toBeEnabled()
  })

  it('cancel closes without submitting', async () => {
    const user = userEvent.setup()
    const { onOpenChange } = renderModal()
    await user.type(screen.getByLabelText('제목'), 'T')
    await user.click(within(screen.getByRole('dialog')).getByRole('button', { name: '취소' }))
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(adapter).not.toHaveBeenCalled()
  })

  it('Escape closes without submitting', async () => {
    const user = userEvent.setup()
    const { onOpenChange } = renderModal()
    await user.keyboard('{Escape}')
    expect(onOpenChange).toHaveBeenCalledWith(false)
    expect(adapter).not.toHaveBeenCalled()
  })

  it('resets the form after it was closed and reopened', async () => {
    const user = userEvent.setup()
    const client = createQueryClient()
    const tree = (open: boolean) => (
      <QueryClientProvider client={client}>
        <CreateProjectModal open={open} onOpenChange={vi.fn()} />
      </QueryClientProvider>
    )
    const { rerender } = render(tree(true))
    await user.type(screen.getByLabelText('제목'), '남은 글')
    await user.click(submit())
    await user.click(screen.getByLabelText('설명'))
    await user.paste('x')
    rerender(tree(false))
    rerender(tree(true))
    expect(screen.getByLabelText('제목')).toHaveValue('')
    expect(screen.getByLabelText('설명')).toHaveValue('')
    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
  })
})
