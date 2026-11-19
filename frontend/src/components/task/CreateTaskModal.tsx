import { useId, useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import FormField from '../auth/FormField'
import { useFormSubmission } from '../auth/useFormSubmission'
import FileUpload from '../upload/FileUpload'
import FolderUpload, { type FolderSelection } from '../upload/FolderUpload'
import PasteCode, { type PasteValue } from '../upload/PasteCode'
import { useCreateTask } from '../../hooks/useTasks'
import { formatFileSize } from '../../lib/task-labels'
import {
  EXCLUDED_NOTICE,
  MAX_DESCRIPTION_LENGTH,
  validatePaste,
  validateTaskDescription,
  validateTaskTitle,
  validateUploadFiles,
} from '../../lib/upload-validation'
import { isApiError } from '../../services/api-client'
import type {
  CreateTaskInput,
  CreateTaskResult,
  TaskUploadInput,
  UploadMethod,
} from '../../services/task-service'

interface CreateTaskModalProps {
  projectId: string
  open: boolean
  onOpenChange: (open: boolean) => void
}

// The dialog content unmounts when closed, so the form starts empty on every opening.
export default function CreateTaskModal({ projectId, open, onOpenChange }: CreateTaskModalProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        aria-describedby={undefined}
        className="max-h-[90vh] overflow-y-auto sm:max-w-xl"
      >
        <TaskCreation projectId={projectId} onClose={() => onOpenChange(false)} />
      </DialogContent>
    </Dialog>
  )
}

interface Created {
  result: CreateTaskResult
  // Paths the browser already left out of a folder upload (the server never saw them).
  clientExcluded: string[]
}

function TaskCreation({ projectId, onClose }: { projectId: string; onClose: () => void }) {
  const idPrefix = useId()
  const create = useCreateTask(projectId)
  const { pending, serverError, submit, clearError } = useFormSubmission(
    'Task를 만들지 못했습니다. 잠시 후 다시 시도하세요.',
  )
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [method, setMethod] = useState<UploadMethod>('file')
  const [files, setFiles] = useState<File[]>([])
  const [folder, setFolder] = useState<FolderSelection>({ entries: [], excludedPaths: [] })
  const [paste, setPaste] = useState<PasteValue>({ code: '', language: '' })
  const [attempted, setAttempted] = useState(false)
  const [errors, setErrors] = useState<{ title?: string; description?: string }>({})
  const [suggestion, setSuggestion] = useState<string | null>(null)
  const [created, setCreated] = useState<Created | null>(null)

  if (created) {
    return <UploadConfirmation {...created} onConfirm={onClose} />
  }

  const uploadError =
    method === 'file'
      ? validateUploadFiles(files)
      : method === 'folder'
        ? validateUploadFiles(folder.entries.map((entry) => entry.file))
        : validatePaste(paste.code, paste.language)
  // File and folder problems are shown as soon as something is chosen; pasted code is
  // only checked once the user tries to submit, so an empty form is not shouting at them.
  const picked = method === 'file' ? files.length : folder.entries.length
  const shownUploadError = attempted || (method !== 'paste' && picked > 0) ? uploadError : undefined

  function uploadInput(): TaskUploadInput {
    if (method === 'file') return { method, files }
    if (method === 'folder') return { method, entries: folder.entries }
    return { method, code: paste.code, language: paste.language }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAttempted(true)
    const found = {
      title: validateTaskTitle(title),
      description: validateTaskDescription(description),
    }
    setErrors(found)
    if (found.title || found.description || uploadError) {
      // The browser's own message is the current one; an earlier server answer is stale.
      clearError()
      setSuggestion(null)
      return
    }
    const trimmedDescription = description.trim()
    const input: CreateTaskInput = {
      title: title.trim(),
      ...(trimmedDescription && { description: trimmedDescription }),
      upload: uploadInput(),
    }
    void submit(async () => {
      setSuggestion(null)
      try {
        const result = await create.mutateAsync(input)
        setCreated({
          result,
          clientExcluded: method === 'folder' ? folder.excludedPaths : [],
        })
      } catch (error) {
        setSuggestion(isApiError(error) ? (error.suggestion ?? null) : null)
        throw error
      }
    })
  }

  const descriptionId = `${idPrefix}-description`
  return (
    <>
      <DialogHeader>
        <DialogTitle>새 Task</DialogTitle>
      </DialogHeader>
      <form noValidate onSubmit={handleSubmit} className="grid gap-4">
        {serverError && (
          <div role="alert" className="grid gap-1 text-sm text-destructive">
            <p>{serverError}</p>
            {suggestion && <p>{suggestion}</p>}
          </div>
        )}
        <FormField
          id={`${idPrefix}-title`}
          label="제목"
          required
          value={title}
          onChange={(event) => setTitle(event.target.value)}
          error={errors.title}
        />
        <div className="grid gap-1.5">
          <Label htmlFor={descriptionId}>설명</Label>
          <Textarea
            id={descriptionId}
            aria-invalid={errors.description ? true : undefined}
            aria-describedby={`${descriptionId}-hint`}
            value={description}
            onChange={(event) => setDescription(event.target.value)}
          />
          <p id={`${descriptionId}-hint`} className="text-sm text-muted-foreground">
            {MAX_DESCRIPTION_LENGTH - description.length}자 남음
          </p>
          {errors.description && <p className="text-sm text-destructive">{errors.description}</p>}
        </div>
        <Tabs value={method} onValueChange={(value) => setMethod(value as UploadMethod)}>
          <TabsList className="w-full">
            <TabsTrigger value="file">파일 업로드</TabsTrigger>
            <TabsTrigger value="folder">폴더 업로드</TabsTrigger>
            <TabsTrigger value="paste">코드 붙여넣기</TabsTrigger>
          </TabsList>
          <TabsContent value="file">
            <FileUpload files={files} onChange={setFiles} error={shownUploadError} />
          </TabsContent>
          <TabsContent value="folder">
            <FolderUpload {...folder} onChange={setFolder} error={shownUploadError} />
          </TabsContent>
          <TabsContent value="paste">
            <PasteCode {...paste} onChange={setPaste} error={shownUploadError} />
          </TabsContent>
        </Tabs>
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onClose}>
            취소
          </Button>
          <Button type="submit" disabled={pending}>
            {pending ? '업로드하는 중...' : 'Task 만들기'}
          </Button>
        </div>
      </form>
    </>
  )
}

// FR-019: after a successful upload, show everything that was stored.
function UploadConfirmation({
  result,
  clientExcluded,
  onConfirm,
}: Created & { onConfirm: () => void }) {
  const excludedCount = clientExcluded.length + result.excluded_paths.length
  return (
    <>
      <DialogHeader>
        <DialogTitle>업로드 확인</DialogTitle>
      </DialogHeader>
      <div className="grid gap-3 text-sm">
        <p>
          <strong>Task {result.task_number}</strong> · {result.title}
        </p>
        <ul aria-label="업로드된 파일" className="grid gap-1">
          {result.files.map((file) => (
            <li key={file.id} className="flex justify-between gap-2">
              <span className="min-w-0 truncate">{file.file_path ?? file.file_name}</span>
              <span className="text-muted-foreground">{formatFileSize(file.file_size_bytes)}</span>
            </li>
          ))}
        </ul>
        {excludedCount > 0 && (
          <p className="text-muted-foreground">
            {EXCLUDED_NOTICE} (제외된 파일 {excludedCount}개)
          </p>
        )}
        {result.warnings.map((warning) => (
          <p key={warning.code} className="text-amber-700 dark:text-amber-400">
            {warning.message}
          </p>
        ))}
      </div>
      <div className="flex justify-end">
        <Button type="button" onClick={onConfirm}>
          확인
        </Button>
      </div>
    </>
  )
}
