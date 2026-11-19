import { useState } from 'react'

import { cn } from '@/lib/utils'
import { codeFileKey, fileMatches } from '../../lib/document-files'
import type { TaskCodeFile } from '../../services/task-service'
import { CodeEditor, type HighlightRequest } from './CodeEditor'

export interface FileHighlight extends HighlightRequest {
  file: string
}

interface CodePanelProps {
  files: TaskCodeFile[]
  // Lines to highlight (in whichever file they name); null shows none.
  highlight: FileHighlight | null
  // First visible line of the file being shown, when the user scrolls or switches files.
  onTopLineChange?: (file: TaskCodeFile, line: number) => void
}

export default function CodePanel({ files, highlight, onTopLineChange }: CodePanelProps) {
  const [shownId, setShownId] = useState(files[0]?.id)
  const [seenHighlight, setSeenHighlight] = useState(highlight)

  // A new highlight request brings its file to the front. This is done while rendering (not
  // in an effect) so the editor never shows the new lines on the wrong file.
  if (highlight !== seenHighlight) {
    setSeenHighlight(highlight)
    const target = highlight && files.find((file) => fileMatches(highlight.file, file))
    if (target) setShownId(target.id)
  }

  const shown = files.find((file) => file.id === shownId) ?? files[0]
  if (!shown) return <p className="p-4 text-muted-foreground">표시할 코드가 없습니다.</p>

  const forShown = highlight && fileMatches(highlight.file, shown) ? highlight : null
  const name = codeFileKey(shown)

  return (
    <div className="grid h-full grid-rows-[auto_1fr] gap-2">
      {files.length > 1 ? (
        <div role="tablist" aria-label="코드 파일" className="flex flex-wrap gap-1">
          {files.map((file) => (
            <button
              key={file.id}
              type="button"
              role="tab"
              aria-selected={file.id === shown.id}
              className={cn(
                'rounded-md px-3 py-1 text-sm',
                file.id === shown.id ? 'bg-primary text-primary-foreground' : 'bg-muted',
              )}
              onClick={() => {
                setShownId(file.id)
                onTopLineChange?.(file, 1)
              }}
            >
              {codeFileKey(file)}
            </button>
          ))}
        </div>
      ) : (
        <p className="text-sm font-medium">{name}</p>
      )}
      <CodeEditor
        code={shown.content}
        language={shown.language}
        label={`${name} 코드`}
        highlight={forShown}
        onTopLineChange={(line) => onTopLineChange?.(shown, line)}
      />
    </div>
  )
}
