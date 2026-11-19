import { QueryClientProvider } from '@tanstack/react-query'
import { act, renderHook, waitFor } from '@testing-library/react'
import type { ReactNode } from 'react'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { useDocumentStatus, useTaskCode, useTaskDocument } from '../../src/hooks/useDocument'
import { createQueryClient } from '../../src/lib/queryClient'
import { errorBody, mockApi, reply, requestKey, respondByRoute } from '../helpers/mock-api'
import { makeDocument, makeStatus, makeTaskCode } from '../helpers/document-fixtures'

const adapter = mockApi()

function setup() {
  const client = createQueryClient()
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return { client, wrapper }
}

const statusCalls = () =>
  adapter.mock.calls.filter(([c]) => requestKey(c) === 'GET /tasks/t-1/document/status').length

afterEach(() => {
  vi.useRealTimers()
})

describe('useDocumentStatus polling', () => {
  async function advance(ms: number) {
    await act(async () => {
      await vi.advanceTimersByTimeAsync(ms)
    })
  }

  it.each(['pending', 'in_progress'] as const)('polls every 2 seconds while %s', async (status) => {
    vi.useFakeTimers()
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus({ status })),
    })
    const { wrapper } = setup()
    renderHook(() => useDocumentStatus('t-1'), { wrapper })
    await advance(0)
    expect(statusCalls()).toBe(1)
    await advance(1900)
    expect(statusCalls()).toBe(1)
    await advance(200)
    expect(statusCalls()).toBe(2)
    await advance(2000)
    expect(statusCalls()).toBe(3)
  })

  it.each(['completed', 'failed'] as const)('does not poll once %s', async (status) => {
    vi.useFakeTimers()
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus({ status })),
    })
    const { wrapper } = setup()
    renderHook(() => useDocumentStatus('t-1'), { wrapper })
    await advance(0)
    await advance(10_000)
    expect(statusCalls()).toBe(1)
  })

  it('stops polling when the status turns completed', async () => {
    vi.useFakeTimers()
    let status: 'pending' | 'completed' = 'pending'
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus({ status })),
    })
    const { wrapper } = setup()
    const { result } = renderHook(() => useDocumentStatus('t-1'), { wrapper })
    await advance(0)
    status = 'completed'
    await advance(2100)
    expect(result.current.data?.status).toBe('completed')
    const before = statusCalls()
    await advance(10_000)
    expect(statusCalls()).toBe(before)
  })

  it('stops polling when the component unmounts', async () => {
    vi.useFakeTimers()
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 200, makeStatus({ status: 'pending' })),
    })
    const { wrapper } = setup()
    const { unmount } = renderHook(() => useDocumentStatus('t-1'), { wrapper })
    await advance(0)
    unmount()
    const before = statusCalls()
    await advance(10_000)
    expect(statusCalls()).toBe(before)
  })

  it('does not poll when there is no document', async () => {
    vi.useFakeTimers()
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) => reply(c, 404, errorBody('document_not_found')),
    })
    const { wrapper } = setup()
    const { result } = renderHook(() => useDocumentStatus('t-1'), { wrapper })
    await advance(0)
    expect(result.current.data).toBeNull()
    await advance(10_000)
    expect(statusCalls()).toBe(1)
  })
})

describe('useTaskDocument', () => {
  it('does not fetch until enabled, then fetches once under ["tasks", id, "document"]', async () => {
    const doc = makeDocument()
    respondByRoute(adapter, { 'GET /tasks/t-1/document': (c) => reply(c, 200, doc) })
    const { client, wrapper } = setup()
    const { result, rerender } = renderHook(({ on }) => useTaskDocument('t-1', on), {
      wrapper,
      initialProps: { on: false },
    })
    expect(adapter).not.toHaveBeenCalled()
    rerender({ on: true })
    await waitFor(() => expect(result.current.data).toEqual(doc))
    expect(client.getQueryData(['tasks', 't-1', 'document'])).toEqual(doc)
    rerender({ on: true })
    expect(adapter).toHaveBeenCalledTimes(1)
  })
})

describe('useTaskCode', () => {
  it('loads the task code under ["tasks", id, "code"] when enabled', async () => {
    const code = makeTaskCode()
    respondByRoute(adapter, { 'GET /tasks/t-1/code': (c) => reply(c, 200, code) })
    const { client, wrapper } = setup()
    const { result } = renderHook(() => useTaskCode('t-1', true), { wrapper })
    await waitFor(() => expect(result.current.data).toEqual(code))
    expect(client.getQueryData(['tasks', 't-1', 'code'])).toEqual(code)
  })

  it('stays idle while disabled', () => {
    const { wrapper } = setup()
    renderHook(() => useTaskCode('t-1', false), { wrapper })
    expect(adapter).not.toHaveBeenCalled()
  })
})
