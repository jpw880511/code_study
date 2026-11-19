import { useState, type FormEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import FormField from '../auth/FormField'
import { useFormSubmission } from '../auth/useFormSubmission'
import {
  MAX_DESCRIPTION_LENGTH,
  validateProjectDescription,
  validateProjectTitle,
} from '../../lib/project-validation'

export interface ProjectFormValues {
  title: string
  description: string
}

interface ProjectFormProps {
  idPrefix: string
  initialValues?: ProjectFormValues
  submitLabel: string
  pendingLabel: string
  onSubmit: (values: ProjectFormValues) => Promise<unknown>
  onCancel: () => void
}

// Shared by the create and edit dialogs. Values reach onSubmit trimmed.
export default function ProjectForm({
  idPrefix,
  initialValues = { title: '', description: '' },
  submitLabel,
  pendingLabel,
  onSubmit,
  onCancel,
}: ProjectFormProps) {
  const [title, setTitle] = useState(initialValues.title)
  const [description, setDescription] = useState(initialValues.description)
  const [errors, setErrors] = useState<{ title?: string; description?: string }>({})
  const { pending, serverError, submit } = useFormSubmission(
    '프로젝트를 저장하지 못했습니다. 잠시 후 다시 시도하세요.',
  )

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const found = {
      title: validateProjectTitle(title),
      description: validateProjectDescription(description),
    }
    setErrors(found)
    if (found.title || found.description) return
    void submit(() => onSubmit({ title: title.trim(), description: description.trim() }))
  }

  const descriptionId = `${idPrefix}-description`
  return (
    <form noValidate onSubmit={handleSubmit} className="grid gap-4">
      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {serverError}
        </p>
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
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onCancel}>
          취소
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? pendingLabel : submitLabel}
        </Button>
      </div>
    </form>
  )
}
