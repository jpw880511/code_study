import { useRef, useState } from 'react'

import { isApiError } from '../../services/api-client'

// Pending/error state for a form's async submit. The ref blocks a second submit that
// arrives before React has re-rendered the disabled button (e.g. a fast double Enter).
export function useFormSubmission(fallbackMessage: string) {
  const [pending, setPending] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const inFlight = useRef(false)

  async function submit(action: () => Promise<unknown>) {
    if (inFlight.current) return
    inFlight.current = true
    setPending(true)
    setServerError(null)
    try {
      await action()
    } catch (error) {
      setServerError(isApiError(error) ? error.message : fallbackMessage)
    } finally {
      inFlight.current = false
      setPending(false)
    }
  }

  // For a form that fails its own checks before submit() runs: the old server answer is stale.
  function clearError() {
    setServerError(null)
  }

  return { pending, serverError, submit, clearError }
}
