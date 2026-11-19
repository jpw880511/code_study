import { useId } from 'react'

import { Label } from '@/components/ui/label'
import { Textarea } from '@/components/ui/textarea'
import { PASTE_LANGUAGES } from '../../lib/upload-validation'

export interface PasteValue {
  code: string
  language: string
}

interface PasteCodeProps extends PasteValue {
  onChange: (value: PasteValue) => void
  error?: string
}

export default function PasteCode({ code, language, onChange, error }: PasteCodeProps) {
  const id = useId()
  return (
    <div className="grid gap-3">
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}-language`}>프로그래밍 언어</Label>
        <select
          id={`${id}-language`}
          value={language}
          onChange={(event) => onChange({ code, language: event.target.value })}
          className="h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 dark:bg-input/30"
        >
          <option value="">언어를 선택하세요</option>
          {PASTE_LANGUAGES.map(({ value, label }) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </div>
      <div className="grid gap-1.5">
        <Label htmlFor={`${id}-code`}>코드</Label>
        <Textarea
          id={`${id}-code`}
          value={code}
          onChange={(event) => onChange({ code: event.target.value, language })}
          spellCheck={false}
          className="min-h-40 font-mono"
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}
