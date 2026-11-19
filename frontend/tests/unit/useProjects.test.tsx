import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { describe, expect, it } from 'vitest'

import {
  useCreateProject,
  useDeleteProject,
  useProject,
  useProjects,
  useUpdateProject,
} from '../../src/hooks/useProjects'
import { createQueryClient } from '../../src/lib/queryClient'
import { mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import { makeProject } from '../helpers/project-fixtures'

const adapter = mockApi()

function setup() {
  const client = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

function requests() {
  return adapter.mock.calls.map(([c]) => requestKey(c))
}

describe('queries', () => {
  it('useProjects loads the list under the ["projects"] key', async () => {
    const list = [makeProject()]
    respondByRoute(adapter, { 'GET /projects': (c) => reply(c, 200, list) })
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useProjects(), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual(list))
    expect(client.getQueryData(['projects'])).toEqual(list)
  })

  it('useProject loads one project under ["projects", id]', async () => {
    const project = makeProject({ id: 'p-9' })
    respondByRoute(adapter, { 'GET /projects/p-9': (c) => reply(c, 200, project) })
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useProject('p-9'), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual(project))
    expect(client.getQueryData(['projects', 'p-9'])).toEqual(project)
  })
})

describe('mutations', () => {
  it('useCreateProject posts and refreshes the list', async () => {
    const created = makeProject({ id: 'new' })
    let list = [makeProject()]
    respondByRoute(adapter, {
      'GET /projects': (c) => reply(c, 200, list),
      'POST /projects': (c) => {
        list = [created, ...list]
        return reply(c, 201, created)
      },
    })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ list: useProjects(), create: useCreateProject() }), {
      wrapper,
    })
    await waitFor(() => expect(result.current.list.data).toHaveLength(1))
    await act(() => result.current.create.mutateAsync({ title: 'T' }))
    await waitFor(() => expect(result.current.list.data).toHaveLength(2))
    expect(requests()).toEqual(['GET /projects', 'POST /projects', 'GET /projects'])
  })

  it('useUpdateProject patches, then refreshes the list and the detail', async () => {
    let project = makeProject({ id: 'p-1', title: 'Old' })
    respondByRoute(adapter, {
      'GET /projects': (c) => reply(c, 200, [project]),
      'GET /projects/p-1': (c) => reply(c, 200, project),
      'PATCH /projects/p-1': (c) => {
        project = { ...project, title: 'New' }
        return reply(c, 200, project)
      },
    })
    const { wrapper } = setup()
    const { result } = renderHook(
      () => ({
        list: useProjects(),
        detail: useProject('p-1'),
        update: useUpdateProject('p-1'),
      }),
      { wrapper },
    )
    await waitFor(() => expect(result.current.detail.data?.title).toBe('Old'))
    await waitFor(() => expect(result.current.list.data?.[0].title).toBe('Old'))
    await act(() => result.current.update.mutateAsync({ title: 'New' }))
    await waitFor(() => expect(result.current.detail.data?.title).toBe('New'))
    await waitFor(() => expect(result.current.list.data?.[0].title).toBe('New'))
  })

  it('useDeleteProject deletes, drops the detail from the cache and refreshes the list', async () => {
    let list = [makeProject({ id: 'p-1' })]
    respondByRoute(adapter, {
      'GET /projects': (c) => reply(c, 200, list),
      'DELETE /projects/p-1': (c) => {
        list = []
        return reply(c, 204)
      },
    })
    const { client, wrapper } = setup()
    client.setQueryData(['projects', 'p-1'], makeProject({ id: 'p-1' }))
    const { result } = renderHook(() => ({ list: useProjects(), del: useDeleteProject() }), {
      wrapper,
    })
    await waitFor(() => expect(result.current.list.data).toHaveLength(1))
    await act(() => result.current.del.mutateAsync('p-1'))
    expect(client.getQueryData(['projects', 'p-1'])).toBeUndefined()
    await waitFor(() => expect(result.current.list.data).toEqual([]))
  })

  it('a failed mutation does not invalidate anything', async () => {
    respondByRoute(adapter, {
      'GET /projects': (c) => reply(c, 200, []),
      'POST /projects': (c) => reply(c, 422, { error: 'invalid_project_title', message: 'x' }),
    })
    const { wrapper } = setup()
    const { result } = renderHook(() => ({ list: useProjects(), create: useCreateProject() }), {
      wrapper,
    })
    await waitFor(() => expect(result.current.list.isSuccess).toBe(true))
    await act(() => result.current.create.mutateAsync({ title: '' }).catch(() => undefined))
    expect(requests()).toEqual(['GET /projects', 'POST /projects'])
  })
})
