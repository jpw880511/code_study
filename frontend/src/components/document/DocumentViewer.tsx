import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { useDocumentStatus, useTaskCode, useTaskDocument } from '../../hooks/useDocument'
import { fileMatches } from '../../lib/document-files'
import { errorMessage } from '../../lib/error-message'
import type { LineExplanation } from '../../services/document-service'
import type { TaskCodeFile } from '../../services/task-service'
import type { ActiveEntry } from './chapters/Chapter4'
import CodePanel, { type FileHighlight } from './CodePanel'
import DocumentStatusView from './DocumentStatusView'
import ExplanationPanel from './ExplanationPanel'

function LoadError({ error, onRetry }: { error: unknown; onRetry: () => void }) {
  return (
    <div className="grid justify-items-start gap-2">
      <p role="alert" className="text-destructive">
        {errorMessage(error, '학습 문서를 불러오지 못했습니다. 잠시 후 다시 시도하세요.')}
      </p>
      <Button type="button" variant="outline" onClick={onRetry}>
        다시 시도
      </Button>
    </div>
  )
}

function contains(entry: LineExplanation, file: TaskCodeFile, line: number): boolean {
  return fileMatches(entry.file, file) && entry.line_start <= line && line <= entry.line_end
}

export default function DocumentViewer({ taskId }: { taskId: string }) {
  const status = useDocumentStatus(taskId)
  const completed = status.data?.status === 'completed'
  const doc = useTaskDocument(taskId, completed)
  const code = useTaskCode(taskId, completed)

  const [active, setActive] = useState<ActiveEntry | null>(null)
  const [highlight, setHighlight] = useState<FileHighlight | null>(null)

  // A failed poll keeps the last known state on screen; only a first load can fail outright.
  if (status.data === undefined) {
    if (status.error) {
      return <LoadError error={status.error} onRetry={() => void status.refetch()} />
    }
    return <p role="status">문서 상태를 확인하는 중...</p>
  }

  if (!completed) return <DocumentStatusView info={status.data} />

  const failure = doc.error ?? code.error
  if (failure) {
    return (
      <LoadError
        error={failure}
        onRetry={() => {
          void doc.refetch()
          void code.refetch()
        }}
      />
    )
  }
  if (doc.data === undefined || code.data === undefined) {
    return <p role="status">학습 문서를 불러오는 중...</p>
  }
  const content = doc.data?.content
  if (!content) {
    return (
      <p role="alert" className="text-destructive">
        학습 문서의 내용을 불러오지 못했습니다.
      </p>
    )
  }

  const entries = content.chapter4.explanations

  // The learner picks an entry: the code panel is told to highlight and show those lines.
  function selectEntry(index: number) {
    const entry = entries[index]
    setActive({ index, source: 'user' })
    setHighlight((previous) => ({
      file: entry.file,
      start: entry.line_start,
      end: entry.line_end,
      nonce: (previous?.nonce ?? 0) + 1,
    }))
  }

  // The learner scrolls the code: the explanation follows. This only ever sets `active`; it
  // never asks the code panel to highlight or scroll, so the two panels cannot chase each
  // other. Lines no entry explains leave the current entry as it is.
  function followCode(file: TaskCodeFile, line: number) {
    setActive((current) => {
      if (current && contains(entries[current.index], file, line)) return current
      const index = entries.findIndex((entry) => contains(entry, file, line))
      return index === -1 ? current : { index, source: 'code' }
    })
  }

  return (
    <section aria-label="학습 문서" className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <h2 className="sr-only">학습 문서</h2>
      <div className="h-[60vh] min-w-0">
        <CodePanel files={code.data.files} highlight={highlight} onTopLineChange={followCode} />
      </div>
      <div className="min-w-0">
        <ExplanationPanel content={content} activeEntry={active} onSelectEntry={selectEntry} />
      </div>
    </section>
  )
}
