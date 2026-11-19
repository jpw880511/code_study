import { useId, type ChangeEvent } from 'react'

import { EXCLUDED_NOTICE, splitExcluded, toFolderEntries } from '../../lib/upload-validation'
import type { FolderEntry } from '../../services/task-service'

export interface FolderSelection {
  entries: FolderEntry[]
  excludedPaths: string[]
}

interface FolderUploadProps extends FolderSelection {
  onChange: (selection: FolderSelection) => void
  error?: string
}

// Folder picker (webkitdirectory). Build/system folders are filtered out here, before
// anything is sent, and the user is told about it.
export default function FolderUpload({
  entries,
  excludedPaths,
  onChange,
  error,
}: FolderUploadProps) {
  const inputId = useId()

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const { kept, excludedPaths: excluded } = splitExcluded(
      toFolderEntries(event.target.files ?? []),
    )
    onChange({ entries: kept, excludedPaths: excluded })
    event.target.value = ''
  }

  return (
    <div className="grid gap-3">
      <label
        htmlFor={inputId}
        className="grid cursor-pointer justify-items-center gap-1 rounded-lg border-2 border-dashed border-input p-6 text-center text-sm focus-within:ring-3 focus-within:ring-ring/50"
      >
        <span className="font-medium">폴더 선택</span>
        <span className="text-muted-foreground">
          클릭해서 폴더를 선택하세요. 폴더 구조가 그대로 유지됩니다.
        </span>
        <input
          id={inputId}
          type="file"
          multiple
          // React's typings lack the non-standard directory attribute, hence the spread.
          {...{ webkitdirectory: '' }}
          className="sr-only"
          onChange={handleChange}
        />
      </label>
      {excludedPaths.length > 0 && (
        <p role="status" className="text-sm text-muted-foreground">
          {EXCLUDED_NOTICE} (제외된 파일 {excludedPaths.length}개)
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
      {entries.length > 0 && (
        <ul aria-label="선택한 폴더 파일" className="grid gap-1 text-sm">
          {entries.map(({ path }) => (
            <li key={path} className="truncate">
              {path}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
