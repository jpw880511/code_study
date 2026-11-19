import { selectIsAuthenticated, useAuthStore, type AuthUser } from '../../stores/auth-store'

// Development-only page for watching the auth store by hand. Not part of the product UI.

const TEST_USER: AuthUser = {
  id: '123',
  email: 'student@example.com',
  skill_level: 'Complete Beginner',
}

// The two panels subscribe to the store separately, so both must update on one change.
function UserPanel() {
  const user = useAuthStore((state) => state.user)
  return (
    <section aria-label="user">
      <h3>user</h3>
      <pre>{user ? JSON.stringify(user, null, 2) : 'null'}</pre>
    </section>
  )
}

function IsAuthenticatedPanel() {
  const isAuthenticated = useAuthStore(selectIsAuthenticated)
  const status = useAuthStore((state) => state.status)
  return (
    <section aria-label="isAuthenticated">
      <h3>isAuthenticated</h3>
      <p>{String(isAuthenticated)}</p>
      <p>status: {status}</p>
    </section>
  )
}

export default function AuthStoreTest() {
  const setUser = useAuthStore((state) => state.setUser)
  const clearUser = useAuthStore((state) => state.clearUser)

  return (
    <div>
      <div>
        <button type="button" onClick={() => setUser(TEST_USER)}>
          사용자 설정
        </button>{' '}
        <button type="button" onClick={clearUser}>
          인증 초기화
        </button>
      </div>
      <UserPanel />
      <IsAuthenticatedPanel />
    </div>
  )
}
