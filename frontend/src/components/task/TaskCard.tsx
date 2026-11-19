import { Link } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate } from '../../lib/format-date'
import { complexityLabel } from '../../lib/task-labels'
import type { Task } from '../../services/task-service'

export default function TaskCard({ task }: { task: Task }) {
  const { upload } = task
  return (
    <Link
      to={`/tasks/${task.id}`}
      className="block rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Card className="transition-shadow hover:shadow-md">
        <CardHeader>
          <p className="text-sm font-medium text-muted-foreground">Task {task.task_number}</p>
          <CardTitle>{task.title}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          {task.description && <p className="line-clamp-3 text-sm">{task.description}</p>}
          {upload ? (
            <p className="text-xs text-muted-foreground">
              {upload.detected_language && `${upload.detected_language} · `}
              {upload.complexity_level && `${complexityLabel(upload.complexity_level)} · `}
              파일 {upload.total_files}개 · {upload.total_lines}줄
            </p>
          ) : (
            <p className="text-xs text-muted-foreground">업로드된 코드가 없습니다.</p>
          )}
          <p className="text-xs text-muted-foreground">{formatDate(task.created_at)}</p>
        </CardContent>
      </Card>
    </Link>
  )
}
