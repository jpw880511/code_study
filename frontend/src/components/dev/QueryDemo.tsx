import { useQuery } from '@tanstack/react-query'
import { useState } from 'react'

import { apiClient, isApiError } from '../../services/api-client'

// Development-only demo of loading / success / error states. Not part of the product UI.

const OPTIONS = [
  { label: '정상', type: null },
  { label: 'notfound', type: 'notfound' },
  { label: 'forbidden', type: 'forbidden' },
  { label: 'conflict', type: 'conflict' },
] as const

type ErrorType = (typeof OPTIONS)[number]['type']

async function fetchTestErrors(type: ErrorType, delayMs: number, signal: AbortSignal) {
  if (delayMs > 0) await new Promise((resolve) => setTimeout(resolve, delayMs))
  const { data } = await apiClient.get('/test-errors', {
    params: type ? { type } : undefined,
    signal,
  })
  return data
}

export default function QueryDemo({ delayMs = 800 }: { delayMs?: number }) {
  const [type, setType] = useState<ErrorType>(null)
  const query = useQuery({
    queryKey: ['test-errors', type ?? 'none'],
    queryFn: ({ signal }) => fetchTestErrors(type, delayMs, signal),
  })

  return (
    <div>
      <p>
        백엔드 <code>/api/v1/test-errors</code> 를 호출합니다.
      </p>

      <div role="group" aria-label="응답 종류">
        {OPTIONS.map((option) => (
          <button
            key={option.label}
            type="button"
            aria-pressed={option.type === type}
            onClick={() => setType(option.type)}
          >
            {option.label}
          </button>
        ))}{' '}
        <button type="button" onClick={() => query.refetch()}>
          다시 불러오기
        </button>
      </div>

      <div role="status">
        {query.isPending && <p>⏳ 로딩 중...</p>}
        {query.isSuccess && (
          <>
            <p>✅ 성공</p>
            <pre>{JSON.stringify(query.data, null, 2)}</pre>
          </>
        )}
        {query.isError && (
          <>
            <p>❌ 에러</p>
            <p>{query.error.message}</p>
            {isApiError(query.error) && (
              <>
                <p>코드: {query.error.code}</p>
                {query.error.status !== undefined && <p>HTTP 상태: {query.error.status}</p>}
              </>
            )}
          </>
        )}
        {!query.isPending && query.isFetching && <p>🔄 갱신 중...</p>}
      </div>
    </div>
  )
}
