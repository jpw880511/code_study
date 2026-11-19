import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useUpdateProject } from '../../hooks/useProjects'
import type { Project } from '../../services/project-service'
import ProjectForm from './ProjectForm'

interface EditProjectModalProps {
  project: Project
  open: boolean
  onOpenChange: (open: boolean) => void
}

export default function EditProjectModal({ project, open, onOpenChange }: EditProjectModalProps) {
  const update = useUpdateProject(project.id)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>프로젝트 수정</DialogTitle>
        </DialogHeader>
        <ProjectForm
          idPrefix="edit-project"
          initialValues={{ title: project.title, description: project.description ?? '' }}
          submitLabel="저장"
          pendingLabel="저장 중..."
          onCancel={() => onOpenChange(false)}
          onSubmit={async ({ title, description }) => {
            await update.mutateAsync({ title, description: description || null })
            onOpenChange(false)
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
