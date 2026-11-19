import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import { useCreateTask, useTask, useTasks } from '../../src/hooks/useTasks'
import { createQueryClient } from '../../src/lib/queryClient'
import { mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import { makeCreateResult, makeFile, makeTask, makeTaskDetail } from '../helpers/task-fixtures'

const adapter = mockApi()

function setup() {
  const client = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

const requests = () => adapter.mock.calls.map(([c]) => requestKey(c))

describe('queries', () => {
  it('useTasks loads a project task list under ["projects", id, "tasks"]', async () => {
    const list = [makeTask()]
    respondByRoute(adapter, { 'GET /projects/p-1/tasks': (c) => reply(c, 200, list) })
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useTasks('p-1'), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual(list))
    expect(client.getQueryData(['projects', 'p-1', 'tasks'])).toEqual(list)
  })

  it('useTask loads one task under ["tasks", id]', async () => {
    const detail = makeTaskDetail({ id: 't-9' })
    respondByRoute(adapter, { 'GET /tasks/t-9': (c) => reply(c, 200, detail) })
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useTask('t-9'), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual(detail))
    expect(client.getQueryData(['tasks', 't-9'])).toEqual(detail)
  })
})

describe('useCreateTask', () => {
  it('posts, then refreshes the task list and invalidates the project and the project list', async () => {
    let created = false
    respondByRoute(adapter, {
      'GET /projects/p-1/tasks': (c) => reply(c, 200, created ? [makeTask()] : []),
      'GET /projects/p-1': (c) => reply(c, 200, { id: 'p-1' }),
      'GET /projects': (c) => reply(c, 200, []),
      'POST /projects/p-1/tasks': (c) => {
        created = true
        return reply(c, 201, makeCreateResult())
      },
    })
    const { client, wrapper } = setup()
    const tasks = renderHook(() => useTasks('p-1'), { wrapper })
    await waitFor(() => expect(tasks.result.current.data).toEqual([]))
    await client.fetchQuery({ queryKey: ['projects', 'p-1'], queryFn: () => ({ id: 'p-1' }) })
    await client.fetchQuery({ queryKey: ['projects'], queryFn: () => [] })
    adapter.mockClear()

    const { result } = renderHook(() => useCreateTask('p-1'), { wrapper })
    await act(() =>
      result.current.mutateAsync({
        title: '제목입니다',
        upload: { method: 'file', files: [makeFile('a.py')] },
      }),
    )
    expect(requests()[0]).toBe('POST /projects/p-1/tasks')
    await waitFor(() => expect(tasks.result.current.data).toEqual([makeTask()]))
    // Not observed here, so they are marked stale and refetch when next shown.
    expect(client.getQueryState(['projects', 'p-1'])?.isInvalidated).toBe(true)
    expect(client.getQueryState(['projects'])?.isInvalidated).toBe(true)
  })
})
