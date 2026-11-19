import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppRoutes } from '../../src/App'
import QueryDemo from '../../src/components/dev/QueryDemo'
import { createQueryClient } from '../../src/lib/queryClient'
import { apiClient } from '../../src/services/api-client'

const originalAdapter = apiClient.defaults.adapter
const adapterMock = vi.fn<(config: InternalAxiosRequestConfig) => Promise<unknown>>()

function reply(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: '', headers: {}, config, request: {} }
  if (status < 400) return Promise.resolve(response)
  return Promise.reject(new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, {}, response))
}

function renderDemo() {
  const client = createQueryClient()
  client.setDefaultOptions({
    ...client.getDefaultOptions(),
    queries: { ...client.getDefaultOptions().queries, retryDelay: 0 },
  })
  return render(
    <QueryClientProvider client={client}>
      <QueryDemo delayMs={0} />
    </QueryClientProvider>,
  )
}

beforeEach(() => {
  adapterMock.mockReset()
  apiClient.defaults.adapter = adapterMock as never
})

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
})

describe('QueryDemo', () => {
  it('shows the loading state first, then the success data', async () => {
    let finish: () => void = () => {}
    adapterMock.mockImplementation(
      (config) =>
        new Promise((resolve) => (finish = () => resolve(reply(config, 200, { status: 'ok' })))),
    )
    renderDemo()

    expect(screen.getByText(/로딩 중/)).toBeInTheDocument()

    finish()
    expect(await screen.findByText(/성공/)).toBeInTheDocument()
    expect(screen.getByText(/"status": "ok"/)).toBeInTheDocument()
    expect(screen.queryByText(/로딩 중/)).not.toBeInTheDocument()
  })

  it('calls the test-errors endpoint without a type first', async () => {
    adapterMock.mockImplementation((config) => reply(config, 200, { status: 'ok' }))
    renderDemo()
    await screen.findByText(/성공/)
    expect(adapterMock).toHaveBeenCalledTimes(1)
    const config = adapterMock.mock.calls[0][0]
    expect(config.url).toBe('/test-errors')
    expect(config.params).toBeUndefined()
  })

  it('shows the API error message and code, without retrying a 404', async () => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) =>
      config.params?.type === 'notfound'
        ? reply(config, 404, { error: 'not_found', message: '요청한 항목을 찾을 수 없습니다.' })
        : reply(config, 200, { status: 'ok' }),
    )
    renderDemo()
    await screen.findByText(/성공/)

    await user.click(screen.getByRole('button', { name: 'notfound' }))

    expect(await screen.findByText(/에러/)).toBeInTheDocument()
    expect(screen.getByText(/요청한 항목을 찾을 수 없습니다\./)).toBeInTheDocument()
    expect(screen.getByText(/not_found/)).toBeInTheDocument()
    expect(screen.getByText(/404/)).toBeInTheDocument()
    expect(adapterMock).toHaveBeenCalledTimes(2) // 1 success + 1 failure, no retry
    expect(adapterMock.mock.calls[1][0].params).toEqual({ type: 'notfound' })
  })

  it.each([
    ['forbidden', 403, 'forbidden', '접근 권한이 없습니다.'],
    ['conflict', 409, 'conflict', '요청이 현재 상태와 충돌합니다.'],
  ])('shows the %s error', async (type, status, code, message) => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) =>
      config.params?.type === type
        ? reply(config, status, { error: code, message })
        : reply(config, 200, {}),
    )
    renderDemo()
    await screen.findByText(/성공/)
    await user.click(screen.getByRole('button', { name: type }))
    expect(await screen.findByText(message)).toBeInTheDocument()
  })

  it('retries a network failure twice before showing the error', async () => {
    adapterMock.mockImplementation((config) =>
      Promise.reject(new AxiosError('Network Error', 'ERR_NETWORK', config)),
    )
    renderDemo()
    expect(await screen.findByText(/에러/)).toBeInTheDocument()
    expect(
      screen.getByText('서버에 연결할 수 없습니다. 네트워크 상태를 확인하세요.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/network_error/)).toBeInTheDocument()
    expect(screen.queryByText(/HTTP 상태/)).not.toBeInTheDocument()
    expect(adapterMock).toHaveBeenCalledTimes(3)
  })

  it('handles a non-JSON server error with the generic message, after retrying', async () => {
    adapterMock.mockImplementation((config) => reply(config, 500, '<html>oops</html>'))
    renderDemo()
    expect(await screen.findByText(/에러/)).toBeInTheDocument()
    expect(
      screen.getByText('요청을 처리하지 못했습니다. 잠시 후 다시 시도하세요.'),
    ).toBeInTheDocument()
    expect(screen.getByText(/500/)).toBeInTheDocument()
    expect(adapterMock).toHaveBeenCalledTimes(3)
  })

  it('serves a fresh cached result without calling the server again', async () => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) =>
      config.params?.type === 'notfound'
        ? reply(config, 404, { error: 'not_found', message: '없음' })
        : reply(config, 200, { status: 'ok' }),
    )
    renderDemo()
    await screen.findByText(/성공/)
    await user.click(screen.getByRole('button', { name: 'notfound' }))
    await screen.findByText(/에러/)

    await user.click(screen.getByRole('button', { name: '정상' }))

    expect(await screen.findByText(/성공/)).toBeInTheDocument()
    expect(adapterMock).toHaveBeenCalledTimes(2) // the first result came from the cache
  })

  it('refetches on demand', async () => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) => reply(config, 200, { status: 'ok' }))
    renderDemo()
    await screen.findByText(/성공/)

    await user.click(screen.getByRole('button', { name: '다시 불러오기' }))

    await waitFor(() => expect(adapterMock).toHaveBeenCalledTimes(2))
  })

  it('marks the selected type', async () => {
    adapterMock.mockImplementation((config) => reply(config, 200, {}))
    renderDemo()
    await screen.findByText(/성공/)
    expect(screen.getByRole('button', { name: '정상' })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByRole('button', { name: 'notfound' })).toHaveAttribute(
      'aria-pressed',
      'false',
    )
  })
})

describe('/dev/query-demo route', () => {
  it('renders the demo inside the app layout', async () => {
    adapterMock.mockImplementation((config) => reply(config, 200, { status: 'ok' }))
    render(
      <QueryClientProvider client={createQueryClient()}>
        <MemoryRouter initialEntries={['/dev/query-demo']}>
          <AppRoutes />
        </MemoryRouter>
      </QueryClientProvider>,
    )
    expect(
      screen.getByRole('heading', { level: 1, name: 'TanStack Query 테스트' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(await screen.findByText(/성공/)).toBeInTheDocument()
  })
})
