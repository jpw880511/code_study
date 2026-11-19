import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { useCreateProject } from '../../hooks/useProjects'
import ProjectForm from './ProjectForm'

interface CreateProjectModalProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

// The dialog content unmounts when closed, so the form starts empty on every opening.
export default function CreateProjectModal({ open, onOpenChange }: CreateProjectModalProps) {
  const create = useCreateProject()
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent aria-describedby={undefined}>
        <DialogHeader>
          <DialogTitle>새 프로젝트</DialogTitle>
        </DialogHeader>
        <ProjectForm
          idPrefix="create-project"
          submitLabel="만들기"
          pendingLabel="만드는 중..."
          onCancel={() => onOpenChange(false)}
          onSubmit={async ({ title, description }) => {
            await create.mutateAsync(description ? { title, description } : { title })
            onOpenChange(false)
          }}
        />
      </DialogContent>
    </Dialog>
  )
}
