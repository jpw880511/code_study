import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import DeleteProjectDialog from '../components/project/DeleteProjectDialog'
import EditProjectModal from '../components/project/EditProjectModal'
import CreateTaskModal from '../components/task/CreateTaskModal'
import TaskCard from '../components/task/TaskCard'
import { useProject } from '../hooks/useProjects'
import { useTasks } from '../hooks/useTasks'
import { errorMessage } from '../lib/error-message'
import { formatDate } from '../lib/format-date'
import { isApiError } from '../services/api-client'

const BACK_TO_DASHBOARD = '대시보드로 돌아가기'

export default function ProjectDetail() {
  const { projectId = '' } = useParams()
  const navigate = useNavigate()
  const [editing, setEditing] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [creatingTask, setCreatingTask] = useState(false)
  const { data: project, isPending, error, refetch } = useProject(projectId)
  const tasks = useTasks(projectId)

  if (isPending) {
    return (
      <p role="status" className="p-4">
        프로젝트를 불러오는 중...
      </p>
    )
  }

  if (error) {
    // 404/403 will not change on a retry, so they only offer the way back.
    const final = isApiError(error) && (error.status === 404 || error.status === 403)
    return (
      <section className="mx-auto grid max-w-3xl justify-items-start gap-3 p-4">
        <p role="alert" className="text-destructive">
          {errorMessage(error, '프로젝트를 불러오지 못했습니다. 잠시 후 다시 시도하세요.')}
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

  return (
    <article className="mx-auto grid max-w-3xl gap-6 p-4">
      <Link to="/" className="text-sm text-primary underline-offset-4 hover:underline">
        ← {BACK_TO_DASHBOARD}
      </Link>
      <header className="grid gap-3">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <h1 className="text-2xl font-semibold">{project.title}</h1>
          <div className="flex gap-2">
            <Button type="button" variant="outline" onClick={() => setEditing(true)}>
              수정
            </Button>
            <Button type="button" variant="destructive" onClick={() => setDeleting(true)}>
              삭제
            </Button>
          </div>
        </div>
        {project.description ? (
          <p className="whitespace-pre-wrap">{project.description}</p>
        ) : (
          <p className="text-muted-foreground">설명이 없습니다.</p>
        )}
        <p className="text-sm text-muted-foreground">생성일: {formatDate(project.created_at)}</p>
        <p className="text-sm text-muted-foreground">
          마지막 활동: {formatDate(project.last_activity_at)}
        </p>
      </header>
      <section aria-labelledby="timeline-heading" className="grid gap-3">
        <div className="flex items-center justify-between gap-3">
          <h2 id="timeline-heading" className="text-lg font-semibold">
            Task 타임라인
          </h2>
          <Button type="button" onClick={() => setCreatingTask(true)}>
            새 Task
          </Button>
        </div>
        {tasks.isPending && <p role="status">Task를 불러오는 중...</p>}
        {tasks.error && (
          <div className="grid justify-items-start gap-2">
            <p role="alert" className="text-destructive">
              {errorMessage(tasks.error, 'Task를 불러오지 못했습니다. 잠시 후 다시 시도하세요.')}
            </p>
            <Button type="button" variant="outline" onClick={() => void tasks.refetch()}>
              다시 시도
            </Button>
          </div>
        )}
        {tasks.data?.length === 0 && (
          <p className="text-muted-foreground">아직 Task가 없습니다. 첫 Task를 만들어 보세요.</p>
        )}
        {tasks.data && tasks.data.length > 0 && (
          <ol aria-label="Task 목록" className="grid gap-3">
            {tasks.data.map((task) => (
              <li key={task.id}>
                <TaskCard task={task} />
              </li>
            ))}
          </ol>
        )}
      </section>
      <CreateTaskModal projectId={project.id} open={creatingTask} onOpenChange={setCreatingTask} />
      <EditProjectModal project={project} open={editing} onOpenChange={setEditing} />
      <DeleteProjectDialog
        projectId={project.id}
        open={deleting}
        onOpenChange={setDeleting}
        onDeleted={() => navigate('/')}
      />
    </article>
  )
}
