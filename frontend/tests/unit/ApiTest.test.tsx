import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AxiosError, type InternalAxiosRequestConfig } from 'axios'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppRoutes } from '../../src/App'
import ApiTest from '../../src/components/dev/ApiTest'
import { apiClient } from '../../src/services/api-client'

const originalAdapter = apiClient.defaults.adapter
const adapterMock = vi.fn<(config: InternalAxiosRequestConfig) => Promise<unknown>>()

function reply(config: InternalAxiosRequestConfig, status: number, data: unknown) {
  const response = { data, status, statusText: '', headers: {}, config, request: {} }
  if (status < 400) return Promise.resolve(response)
  return Promise.reject(new AxiosError('Request failed', 'ERR_BAD_REQUEST', config, {}, response))
}

function responseArea() {
  return screen.getByRole('region', { name: '응답' })
}

beforeEach(() => {
  adapterMock.mockReset()
  apiClient.defaults.adapter = adapterMock as never
})

afterEach(() => {
  apiClient.defaults.adapter = originalAdapter
})

describe('ApiTest', () => {
  it('starts with a button and an empty response area, without calling the server', () => {
    render(<ApiTest />)
    expect(screen.getByRole('button', { name: 'API 호출' })).toBeEnabled()
    expect(within(responseArea()).getByText('아직 호출하지 않았습니다.')).toBeInTheDocument()
    expect(adapterMock).not.toHaveBeenCalled()
  })

  it('calls GET /health when the button is clicked', async () => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) => reply(config, 200, { status: 'ok' }))
    render(<ApiTest />)

    await user.click(screen.getByRole('button', { name: 'API 호출' }))

    expect(adapterMock).toHaveBeenCalledTimes(1)
    const config = adapterMock.mock.calls[0][0]
    expect(config.method).toBe('get')
    expect(config.url).toBe('/health')
  })

  it('shows the HTTP status and body of a successful response', async () => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) => reply(config, 200, { status: 'ok' }))
    render(<ApiTest />)

    await user.click(screen.getByRole('button', { name: 'API 호출' }))

    const area = responseArea()
    expect(await within(area).findByText('HTTP 200')).toBeInTheDocument()
    expect(within(area).getByText(/"status": "ok"/)).toBeInTheDocument()
    expect(within(area).queryByText('아직 호출하지 않았습니다.')).not.toBeInTheDocument()
  })

  it('shows a loading message and disables the button while waiting', async () => {
    const user = userEvent.setup()
    let finish: () => void = () => {}
    adapterMock.mockImplementation(
      (config) =>
        new Promise((resolve) => (finish = () => resolve(reply(config, 200, { status: 'ok' })))),
    )
    render(<ApiTest />)

    await user.click(screen.getByRole('button', { name: 'API 호출' }))

    expect(within(responseArea()).getByText('호출 중...')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'API 호출' })).toBeDisabled()

    finish()
    expect(await within(responseArea()).findByText('HTTP 200')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'API 호출' })).toBeEnabled()
    expect(within(responseArea()).queryByText('호출 중...')).not.toBeInTheDocument()
  })

  it('shows the message, code and status of an API error', async () => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) =>
      reply(config, 503, { error: 'http_error', message: '요청을 처리할 수 없습니다.' }),
    )
    render(<ApiTest />)

    await user.click(screen.getByRole('button', { name: 'API 호출' }))

    const area = responseArea()
    expect(await within(area).findByText('요청을 처리할 수 없습니다.')).toBeInTheDocument()
    expect(within(area).getByText('코드: http_error')).toBeInTheDocument()
    expect(within(area).getByText('HTTP 503')).toBeInTheDocument()
  })

  it('shows a network failure without an HTTP status', async () => {
    const user = userEvent.setup()
    adapterMock.mockImplementation((config) =>
      Promise.reject(new AxiosError('Network Error', 'ERR_NETWORK', config)),
    )
    render(<ApiTest />)

    await user.click(screen.getByRole('button', { name: 'API 호출' }))

    const area = responseArea()
    expect(
      await within(area).findByText('서버에 연결할 수 없습니다. 네트워크 상태를 확인하세요.'),
    ).toBeInTheDocument()
    expect(within(area).getByText('코드: network_error')).toBeInTheDocument()
    expect(within(area).queryByText(/^HTTP /)).not.toBeInTheDocument()
  })

  it('replaces an earlier result with the newest one', async () => {
    const user = userEvent.setup()
    adapterMock
      .mockImplementationOnce((config) =>
        reply(config, 500, { error: 'internal_error', message: '서버 오류' }),
      )
      .mockImplementationOnce((config) => reply(config, 200, { status: 'ok' }))
    render(<ApiTest />)

    await user.click(screen.getByRole('button', { name: 'API 호출' }))
    expect(await within(responseArea()).findByText('서버 오류')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'API 호출' }))
    expect(await within(responseArea()).findByText('HTTP 200')).toBeInTheDocument()
    expect(within(responseArea()).queryByText('서버 오류')).not.toBeInTheDocument()
    expect(adapterMock).toHaveBeenCalledTimes(2)
  })
})

describe('/dev-test route', () => {
  it('renders the test page inside the app layout', () => {
    render(
      <MemoryRouter initialEntries={['/dev-test']}>
        <AppRoutes />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'API 테스트' })).toBeInTheDocument()
    expect(screen.getByRole('navigation')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'API 호출' })).toBeInTheDocument()
  })
})
