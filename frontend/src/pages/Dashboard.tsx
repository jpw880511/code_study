import { useState } from 'react'

import { Button } from '@/components/ui/button'
import CreateProjectModal from '../components/project/CreateProjectModal'
import ProjectCard from '../components/project/ProjectCard'
import { useProjects } from '../hooks/useProjects'
import { errorMessage } from '../lib/error-message'

export default function Dashboard() {
  const [creating, setCreating] = useState(false)
  const { data: projects, isPending, error, refetch } = useProjects()

  const newProjectButton = (
    <Button type="button" onClick={() => setCreating(true)}>
      새 프로젝트
    </Button>
  )

  return (
    <section className="mx-auto grid max-w-6xl gap-6 p-4">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold">대시보드</h1>
        {newProjectButton}
      </header>
      {isPending && <p role="status">프로젝트를 불러오는 중...</p>}
      {error && (
        <div className="grid justify-items-start gap-2">
          <p role="alert" className="text-destructive">
            {errorMessage(error, '프로젝트를 불러오지 못했습니다. 잠시 후 다시 시도하세요.')}
          </p>
          <Button type="button" variant="outline" onClick={() => void refetch()}>
            다시 시도
          </Button>
        </div>
      )}
      {projects?.length === 0 && (
        <div className="grid justify-items-start gap-3">
          <p>아직 프로젝트가 없습니다. 첫 프로젝트를 만들어 보세요.</p>
          {newProjectButton}
        </div>
      )}
      {projects && projects.length > 0 && (
        <ul
          aria-label="프로젝트 목록"
          className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3"
        >
          {projects.map((project) => (
            <li key={project.id}>
              <ProjectCard project={project} />
            </li>
          ))}
        </ul>
      )}
      <CreateProjectModal open={creating} onOpenChange={setCreating} />
    </section>
  )
}
