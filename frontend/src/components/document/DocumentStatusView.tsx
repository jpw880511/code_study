import type { DocumentStatusInfo } from '../../services/document-service'

// While generating, the bar never reaches 100: the estimate is rough, and "full but still
// waiting" would look broken.
const MAX_IN_PROGRESS_PERCENT = 99

function remainingText(info: DocumentStatusInfo): string | null {
  if (info.elapsed_seconds === null || info.estimated_total_seconds === null) return null
  const remaining = Math.max(0, info.estimated_total_seconds - info.elapsed_seconds)
  return remaining === 0 ? '곧 완료됩니다' : `약 ${remaining}초 남음`
}

function percent(info: DocumentStatusInfo): number | undefined {
  if (info.elapsed_seconds === null || !info.estimated_total_seconds) return undefined
  const done = Math.round((info.elapsed_seconds / info.estimated_total_seconds) * 100)
  return Math.min(MAX_IN_PROGRESS_PERCENT, Math.max(0, done))
}

// What the learner sees instead of the document: no document, queued, generating, or failed.
// Completed documents are shown by the viewer itself.
export default function DocumentStatusView({ info }: { info: DocumentStatusInfo | null }) {
  if (info === null) {
    return <p className="text-muted-foreground">아직 학습 문서가 없습니다.</p>
  }

  if (info.status === 'failed') {
    return (
      <p role="alert" className="text-destructive">
        {info.error ?? '문서를 만들지 못했습니다.'}
      </p>
    )
  }

  const notice = info.notice && <p className="text-sm text-muted-foreground">{info.notice}</p>

  if (info.status === 'pending') {
    return (
      <div className="grid gap-2">
        <p role="status">문서 생성을 기다리는 중</p>
        {notice}
      </div>
    )
  }

  const value = percent(info)
  const remaining = remainingText(info)
  return (
    <div className="grid gap-2">
      <p>문서를 만드는 중입니다.</p>
      <div
        role="progressbar"
        aria-label="문서 생성 진행률"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value}
        className="h-2 w-full overflow-hidden rounded-full bg-muted"
      >
        <div className="h-full bg-primary transition-all" style={{ width: `${value ?? 0}%` }} />
      </div>
      {remaining && <p className="text-sm text-muted-foreground">{remaining}</p>}
      {notice}
    </div>
  )
}
