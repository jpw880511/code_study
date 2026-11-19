import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { useDeleteProject } from '../../hooks/useProjects'
import { errorMessage } from '../../lib/error-message'

interface DeleteProjectDialogProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
  onDeleted: () => void
}

export default function DeleteProjectDialog({
  projectId,
  open,
  onOpenChange,
  onDeleted,
}: DeleteProjectDialogProps) {
  const remove = useDeleteProject()

  function confirm() {
    remove.mutate(projectId, { onSuccess: onDeleted })
  }

  return (
    <Dialog
      open={open}
      onOpenChange={() => {
        remove.reset()
        onOpenChange(false)
      }}
    >
      <DialogContent>
        <DialogHeader>
          <DialogTitle>프로젝트 삭제</DialogTitle>
          <DialogDescription>
            이 프로젝트를 삭제할까요? 프로젝트와 안의 모든 Task가 휴지통으로 이동하며 30일 동안
            복구할 수 있습니다.
          </DialogDescription>
        </DialogHeader>
        {remove.isError && (
          <p role="alert" className="text-sm text-destructive">
            {errorMessage(remove.error, '프로젝트를 삭제하지 못했습니다. 잠시 후 다시 시도하세요.')}
          </p>
        )}
        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            취소
          </Button>
          <Button type="button" variant="destructive" disabled={remove.isPending} onClick={confirm}>
            {remove.isPending ? '삭제 중...' : '삭제'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
