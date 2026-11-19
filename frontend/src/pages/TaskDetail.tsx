import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import DocumentViewer from '@/components/document/DocumentViewer'
import { cn } from '@/lib/utils'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { useTask } from '../hooks/useTasks'
import { errorMessage } from '../lib/error-message'
import { complexityLabel, formatFileSize } from '../lib/task-labels'
import { isApiError } from '../services/api-client'

const BACK_TO_DASHBOARD = '대시보드로 돌아가기'

const TABS = [
  { value: 'document', label: '문서' },
  { value: 'practice', label: '연습문제' },
  { value: 'qa', label: 'Q&A' },
]

// The task page: header, uploaded files and the three feature tabs. The document tab shows the
// learning document; the other two stay placeholders until their own tasks are built.
export default function TaskDetail() {
  const { taskId = '' } = useParams()
  const { data: task, isPending, error, refetch } = useTask(taskId)
  const [tab, setTab] = useState('document')

  if (isPending) {
    return (
      <p role="status" className="p-4">
        Task를 불러오는 중...
      </p>
    )
  }

  if (error) {
    // 404/403 will not change on a retry, so they only offer the way back.
    const final = isApiError(error) && (error.status === 404 || error.status === 403)
    return (
      <section className="mx-auto grid max-w-3xl justify-items-start gap-3 p-4">
        <p role="alert" className="text-destructive">
          {errorMessage(error, 'Task를 불러오지 못했습니다. 잠시 후 다시 시도하세요.')}
        </p>
        {final ? (
          <Link to="/" className="text-primary underline-offset-4 hover:underline">
            {BACK_TO_DASHBOARD}
          </Link>
        ) : (
          <Button type="button" variant="outline" onClick={() => void refetch()}>
            다시 시도
          </Button>
        )}
      </section>
    )
  }

  const { upload } = task
  return (
    // The document tab holds two columns (code and explanation), so it gets a wider page.
    <article
      className={cn('mx-auto grid gap-6 p-4', tab === 'document' ? 'max-w-7xl' : 'max-w-3xl')}
    >
      <Link
        to={`/projects/${task.project_id}`}
        className="text-sm text-primary underline-offset-4 hover:underline"
      >
        ← 프로젝트로 돌아가기
      </Link>
      <header className="grid gap-2">
        <p className="text-sm font-medium text-muted-foreground">Task {task.task_number}</p>
        <h1 className="text-2xl font-semibold">{task.title}</h1>
        {task.description ? (
          <p className="whitespace-pre-wrap">{task.description}</p>
        ) : (
          <p className="text-muted-foreground">설명이 없습니다.</p>
        )}
        {upload ? (
          <div className="flex flex-wrap gap-4 text-sm text-muted-foreground">
            {upload.detected_language && <p>언어: {upload.detected_language}</p>}
            {upload.complexity_level && <p>복잡도: {complexityLabel(upload.complexity_level)}</p>}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">업로드된 코드가 없습니다.</p>
        )}
      </header>
      {task.files.length > 0 && (
        <section aria-labelledby="files-heading" className="grid gap-2">
          <h2 id="files-heading" className="text-lg font-semibold">
            업로드된 파일
          </h2>
          <ul aria-label="업로드된 파일" className="grid gap-1 text-sm">
            {task.files.map((file) => (
              <li key={file.id} className="flex justify-between gap-2">
                <span className="min-w-0 truncate">{file.file_path ?? file.file_name}</span>
                <span className="text-muted-foreground">
                  {formatFileSize(file.file_size_bytes)}
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          {TABS.map(({ value, label }) => (
            <TabsTrigger key={value} value={value}>
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        {TABS.map(({ value, label }) => (
          <TabsContent key={value} value={value}>
            {value === 'document' ? (
              <DocumentViewer taskId={task.id} />
            ) : (
              <p className="text-muted-foreground">{label} 기능은 준비 중입니다.</p>
            )}
          </TabsContent>
        ))}
      </Tabs>
    </article>
  )
}
