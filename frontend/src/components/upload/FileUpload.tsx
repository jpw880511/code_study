import { useId, useState, type ChangeEvent, type DragEvent } from 'react'

import { Button } from '@/components/ui/button'
import { formatFileSize } from '../../lib/task-labels'

interface FileUploadProps {
  files: File[]
  onChange: (files: File[]) => void
  error?: string
}

function sameFile(a: File, b: File) {
  return a.name === b.name && a.size === b.size && a.lastModified === b.lastModified
}

// Drag-and-drop zone plus file picker. The zone is a label around a visually hidden file
// input, so the keyboard can focus the input and open the picker without extra handlers.
export default function FileUpload({ files, onChange, error }: FileUploadProps) {
  const inputId = useId()
  const [dragging, setDragging] = useState(false)

  function add(picked: File[]) {
    const fresh = picked.filter((file) => !files.some((existing) => sameFile(existing, file)))
    if (fresh.length > 0) onChange([...files, ...fresh])
  }

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    add(Array.from(event.target.files ?? []))
    event.target.value = '' // lets the same file be picked again after removing it
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault()
    setDragging(false)
    add(Array.from(event.dataTransfer.files))
  }

  return (
    <div className="grid gap-3">
      <label
        htmlFor={inputId}
        data-testid="file-drop-zone"
        data-dragging={dragging}
        onDragOver={(event) => {
          event.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
        className="grid cursor-pointer justify-items-center gap-1 rounded-lg border-2 border-dashed border-input p-6 text-center text-sm focus-within:ring-3 focus-within:ring-ring/50 data-[dragging=true]:border-primary data-[dragging=true]:bg-muted"
      >
        <span className="font-medium">파일 선택</span>
        <span className="text-muted-foreground">
          여기에 파일을 끌어다 놓거나 클릭해서 선택하세요. (여러 개 선택 가능)
        </span>
        <input id={inputId} type="file" multiple className="sr-only" onChange={handleChange} />
      </label>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {files.length > 0 && (
        <ul aria-label="선택한 파일" className="grid gap-1 text-sm">
          {files.map((file) => (
            <li
              key={`${file.name}-${file.size}-${file.lastModified}`}
              className="flex items-center justify-between gap-2"
            >
              <span className="min-w-0 truncate">
                <span>{file.name}</span>{' '}
                <span className="text-muted-foreground">{formatFileSize(file.size)}</span>
              </span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                aria-label={`${file.name} 제거`}
                onClick={() => onChange(files.filter((other) => other !== file))}
              >
                제거
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
