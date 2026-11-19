import type { ReactNode } from 'react'

import { useAuthBootstrap } from '../../hooks/useAuth'

// Mounted once, above the router, so the session lifecycle (start-up check, periodic and
// reactive token refresh) lives exactly as long as the app and does not depend on which
// route is shown.
export default function AuthProvider({ children }: { children: ReactNode }) {
  useAuthBootstrap()
  return children
}
