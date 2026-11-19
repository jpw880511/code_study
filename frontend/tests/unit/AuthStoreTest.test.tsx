import { act, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it } from 'vitest'

import { AppRoutes } from '../../src/App'
import AuthStoreTest from '../../src/components/dev/AuthStoreTest'
import { useAuthStore } from '../../src/stores/auth-store'

beforeEach(() => {
  useAuthStore.setState(useAuthStore.getInitialState(), true)
})

function userPanel() {
  return screen.getByRole('region', { name: 'user' })
}

function authPanel() {
  return screen.getByRole('region', { name: 'isAuthenticated' })
}

describe('AuthStoreTest', () => {
  it('shows the logged-out state in both components at first', () => {
    render(<AuthStoreTest />)
    expect(within(userPanel()).getByText('null')).toBeInTheDocument()
    expect(within(authPanel()).getByText('false')).toBeInTheDocument()
    expect(within(authPanel()).getByText('status: unknown')).toBeInTheDocument()
  })

  it('updates both components at once when "사용자 설정" is clicked', async () => {
    const user = userEvent.setup()
    render(<AuthStoreTest />)

    await user.click(screen.getByRole('button', { name: '사용자 설정' }))

    expect(within(userPanel()).getByText(/"email": "student@example.com"/)).toBeInTheDocument()
    expect(within(userPanel()).getByText(/"id": "123"/)).toBeInTheDocument()
    expect(within(userPanel()).queryByText('null')).not.toBeInTheDocument()
    expect(within(authPanel()).getByText('true')).toBeInTheDocument()
    expect(within(authPanel()).getByText('status: authenticated')).toBeInTheDocument()
  })

  it('writes the test user into the real store', async () => {
    const user = userEvent.setup()
    render(<AuthStoreTest />)

    await user.click(screen.getByRole('button', { name: '사용자 설정' }))

    expect(useAuthStore.getState().user).toEqual({
      id: '123',
      email: 'student@example.com',
      skill_level: 'Complete Beginner',
    })
    expect(useAuthStore.getState().status).toBe('authenticated')
  })

  it('resets both components at once when "인증 초기화" is clicked', async () => {
    const user = userEvent.setup()
    render(<AuthStoreTest />)
    await user.click(screen.getByRole('button', { name: '사용자 설정' }))

    await user.click(screen.getByRole('button', { name: '인증 초기화' }))

    expect(within(userPanel()).getByText('null')).toBeInTheDocument()
    expect(within(authPanel()).getByText('false')).toBeInTheDocument()
    expect(within(authPanel()).getByText('status: unauthenticated')).toBeInTheDocument()
    expect(useAuthStore.getState().user).toBeNull()
  })

  it('can be clicked repeatedly in any order', async () => {
    const user = userEvent.setup()
    render(<AuthStoreTest />)
    const set = screen.getByRole('button', { name: '사용자 설정' })
    const clear = screen.getByRole('button', { name: '인증 초기화' })

    await user.click(set)
    await user.click(set)
    expect(within(authPanel()).getByText('true')).toBeInTheDocument()
    await user.click(clear)
    await user.click(clear)
    expect(within(authPanel()).getByText('false')).toBeInTheDocument()
    await user.click(set)
    expect(within(userPanel()).getByText(/student@example.com/)).toBeInTheDocument()
  })

  it('also follows changes made outside the buttons (shared store)', () => {
    render(<AuthStoreTest />)

    act(() =>
      useAuthStore
        .getState()
        .setUser({ id: '7', email: 'other@example.com', skill_level: 'Advanced' }),
    )

    expect(within(userPanel()).getByText(/other@example.com/)).toBeInTheDocument()
    expect(within(authPanel()).getByText('true')).toBeInTheDocument()
  })

  it('shows the same store in two separate mounted copies', async () => {
    const user = userEvent.setup()
    render(
      <>
        <section aria-label="copy-1">
          <AuthStoreTest />
        </section>
        <section aria-label="copy-2">
          <AuthStoreTest />
        </section>
      </>,
    )
    const [firstSet] = screen.getAllByRole('button', { name: '사용자 설정' })

    await user.click(firstSet)

    for (const name of ['copy-1', 'copy-2']) {
      const copy = within(screen.getByRole('region', { name }))
      expect(copy.getByText(/student@example.com/)).toBeInTheDocument()
      expect(copy.getByText('true')).toBeInTheDocument()
    }
  })
})

describe('/dev-test route', () => {
  it('shows the store test below the API test', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/dev-test']}>
        <AppRoutes />
      </MemoryRouter>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'API 테스트' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'API 호출' })).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { level: 2, name: 'Zustand 인증 스토어 테스트' }),
    ).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: '사용자 설정' }))
    expect(within(authPanel()).getByText('true')).toBeInTheDocument()
  })
})
