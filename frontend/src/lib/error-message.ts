import { isApiError } from '../services/api-client'

// The server's message for API errors; the caller's fallback for anything else.
export function errorMessage(error: unknown, fallback: string): string {
  return isApiError(error) ? error.message : fallback
}
