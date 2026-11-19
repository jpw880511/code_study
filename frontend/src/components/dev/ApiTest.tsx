import { useState } from 'react'

import { apiClient, isApiError } from '../../services/api-client'

// Development-only page for trying the API client by hand. Not part of the product UI.

type Result =
  | { kind: 'idle' }
  | { kind: 'loading' }
  | { kind: 'success'; status: number; data: unknown }
  | { kind: 'error'; error: unknown }

export default function ApiTest() {
  const [result, setResult] = useState<Result>({ kind: 'idle' })

  async function callApi() {
    setResult({ kind: 'loading' })
    try {
      const response = await apiClient.get('/health')
      setResult({ kind: 'success', status: response.status, data: response.data })
    } catch (error) {
      setResult({ kind: 'error', error })
    }
  }

  return (
    <div>
      <button type="button" onClick={callApi} disabled={result.kind === 'loading'}>
        API 호출
      </button>

      <section aria-label="응답">
        {result.kind === 'idle' && <p>아직 호출하지 않았습니다.</p>}
        {result.kind === 'loading' && <p>호출 중...</p>}
        {result.kind === 'success' && (
          <>
            <p>HTTP {result.status}</p>
            <pre>{JSON.stringify(result.data, null, 2)}</pre>
          </>
        )}
        {result.kind === 'error' && (
          <>
            <p>{result.error instanceof Error ? result.error.message : String(result.error)}</p>
            {isApiError(result.error) && (
              <>
                <p>코드: {result.error.code}</p>
                {result.error.status !== undefined && <p>HTTP {result.error.status}</p>}
              </>
            )}
          </>
        )}
      </section>
    </div>
  )
}
