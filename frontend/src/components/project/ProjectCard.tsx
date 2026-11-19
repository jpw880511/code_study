import { Link } from 'react-router-dom'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatDate } from '../../lib/format-date'
import type { Project } from '../../services/project-service'

export default function ProjectCard({ project }: { project: Project }) {
  return (
    <Link
      to={`/projects/${project.id}`}
      className="block rounded-xl outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
    >
      <Card className="h-full transition-shadow hover:shadow-md">
        <CardHeader>
          <CardTitle>{project.title}</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-2">
          {project.description && (
            <p data-testid="project-card-description" className="line-clamp-3 text-sm">
              {project.description}
            </p>
          )}
          <p className="text-xs text-muted-foreground">
            마지막 활동: {formatDate(project.last_activity_at)}
          </p>
        </CardContent>
      </Card>
    </Link>
  )
}
