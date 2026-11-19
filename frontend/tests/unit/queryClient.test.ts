import { QueryClient } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'

import {
  createQueryClient,
  getErrorStatus,
  queryClient,
  shouldRetry,
} from '../../src/lib/queryClient'

function httpError(status: number) {
  return { response: { status } }
}

describe('getErrorStatus', () => {
  it('reads the status from an axios-style error', () => {
    expect(getErrorStatus(httpError(404))).toBe(404)
  })

  it('reads a top-level status', () => {
    expect(getErrorStatus({ status: 409 })).toBe(409)
  })

  it.each([new Error('network down'), null, undefined, 'oops', { response: {} }])(
    'returns undefined when there is no status (%s)',
    (error) => {
      expect(getErrorStatus(error)).toBeUndefined()
    },
  )
})

describe('shouldRetry', () => {
  it.each([400, 401, 403, 404, 409, 422, 429])('never retries a %i client error', (status) => {
    expect(shouldRetry(0, httpError(status))).toBe(false)
  })

  it.each([500, 502, 503])('retries a %i server error up to twice', (status) => {
    expect(shouldRetry(0, httpError(status))).toBe(true)
    expect(shouldRetry(1, httpError(status))).toBe(true)
    expect(shouldRetry(2, httpError(status))).toBe(false)
  })

  it('retries errors without a status (network failures) up to twice', () => {
    expect(shouldRetry(0, new Error('Network Error'))).toBe(true)
    expect(shouldRetry(1, new Error('Network Error'))).toBe(true)
    expect(shouldRetry(2, new Error('Network Error'))).toBe(false)
  })
})

describe('query client defaults', () => {
  it('is a QueryClient singleton', () => {
    expect(queryClient).toBeInstanceOf(QueryClient)
    expect(queryClient).toBe(queryClient)
  })

  it('creates independent clients for tests', () => {
    expect(createQueryClient()).not.toBe(createQueryClient())
    expect(createQueryClient()).not.toBe(queryClient)
  })

  it('keeps data fresh for one minute and does not refetch on window focus', () => {
    const { queries } = createQueryClient().getDefaultOptions()
    expect(queries?.staleTime).toBe(60_000)
    expect(queries?.refetchOnWindowFocus).toBe(false)
  })

  it('does not retry mutations', () => {
    expect(createQueryClient().getDefaultOptions().mutations?.retry).toBe(false)
  })

  it('backs off exponentially and caps the delay', () => {
    const retryDelay = createQueryClient().getDefaultOptions().queries?.retryDelay
    expect(typeof retryDelay).toBe('function')
    const delay = retryDelay as (attempt: number, error: unknown) => number
    expect([0, 1, 2].map((attempt) => delay(attempt, null))).toEqual([1000, 2000, 4000])
    expect(delay(20, null)).toBe(10_000)
  })
})

describe('query client behavior', () => {
  function fastClient() {
    const client = createQueryClient()
    client.setDefaultOptions({
      ...client.getDefaultOptions(),
      queries: { ...client.getDefaultOptions().queries, retryDelay: 0 },
    })
    return client
  }

  it('does not retry a 404', async () => {
    const queryFn = vi.fn().mockRejectedValue(httpError(404))
    await expect(fastClient().fetchQuery({ queryKey: ['a'], queryFn })).rejects.toBeDefined()
    expect(queryFn).toHaveBeenCalledTimes(1)
  })

  it('retries a 500 and succeeds on the next attempt', async () => {
    const queryFn = vi.fn().mockRejectedValueOnce(httpError(500)).mockResolvedValue('ok')
    await expect(fastClient().fetchQuery({ queryKey: ['b'], queryFn })).resolves.toBe('ok')
    expect(queryFn).toHaveBeenCalledTimes(2)
  })

  it('gives up after two retries (three calls in total)', async () => {
    const queryFn = vi.fn().mockRejectedValue(httpError(503))
    await expect(fastClient().fetchQuery({ queryKey: ['c'], queryFn })).rejects.toBeDefined()
    expect(queryFn).toHaveBeenCalledTimes(3)
  })

  it('runs a failing mutation only once', async () => {
    const mutationFn = vi.fn().mockRejectedValue(httpError(500))
    const mutation = fastClient().getMutationCache().build(fastClient(), { mutationFn })
    await expect(mutation.execute(undefined)).rejects.toBeDefined()
    expect(mutationFn).toHaveBeenCalledTimes(1)
  })

  it('serves cached data without calling the server again while fresh', async () => {
    const client = fastClient()
    const queryFn = vi.fn().mockResolvedValue('data')
    await client.fetchQuery({ queryKey: ['d'], queryFn })
    await client.fetchQuery({ queryKey: ['d'], queryFn })
    expect(queryFn).toHaveBeenCalledTimes(1)
  })
})
