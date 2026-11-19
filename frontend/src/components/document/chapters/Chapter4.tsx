import { useEffect, useRef } from 'react'

import { cn } from '@/lib/utils'
import type { Chapter4 as Chapter4Content } from '../../../services/document-service'

// "code": the code panel scrolled to this entry; "user": the learner chose it here.
export interface ActiveEntry {
  index: number
  source: 'code' | 'user'
}

interface Chapter4Props {
  chapter: Chapter4Content
  active: ActiveEntry | null
  onSelect: (index: number) => void
}

function lineLabel(start: number, end: number): string {
  return start === end ? `${start}줄` : `${start}~${end}줄`
}

function Detail({ label, text }: { label: string; text: string }) {
  if (!text) return null
  return (
    <div>
      <p className="font-medium">{label}</p>
      <p className="whitespace-pre-wrap">{text}</p>
    </div>
  )
}

export default function Chapter4({ chapter, active, onSelect }: Chapter4Props) {
  const items = useRef<(HTMLLIElement | null)[]>([])

  // Only a move made by the code panel brings the entry into view: an entry the learner just
  // chose is already where they are looking.
  useEffect(() => {
    if (active?.source === 'code') {
      items.current[active.index]?.scrollIntoView?.({ block: 'nearest' })
    }
  }, [active])

  return (
    <section className="grid gap-3">
      <h3 className="text-lg font-semibold">{chapter.title}</h3>
      {chapter.explanations.length === 0 ? (
        <p className="text-muted-foreground">줄별 설명이 없습니다.</p>
      ) : (
        <ul className="grid gap-3">
          {chapter.explanations.map((entry, index) => {
            const label = `${entry.file} ${lineLabel(entry.line_start, entry.line_end)}`
            const isActive = active?.index === index
            return (
              <li
                key={`${entry.file}:${entry.line_start}:${entry.line_end}:${index}`}
                ref={(element) => {
                  items.current[index] = element
                }}
                aria-label={label}
                className={cn(
                  'grid cursor-pointer gap-2 rounded-lg border p-3 text-sm',
                  isActive && 'border-primary bg-accent',
                )}
                onClick={() => onSelect(index)}
              >
                <button
                  type="button"
                  aria-label={`${label} 코드에서 보기`}
                  aria-current={isActive ? 'true' : undefined}
                  className="justify-self-start rounded-md font-medium underline-offset-4 hover:underline"
                  onFocus={() => onSelect(index)}
                >
                  {label}
                </button>
                <pre className="overflow-x-auto rounded-md bg-muted p-2 font-mono whitespace-pre-wrap">
                  {entry.code}
                </pre>
                <p className="whitespace-pre-wrap">{entry.what_it_does}</p>
                <Detail label="문법 분석" text={entry.syntax_breakdown} />
                <Detail label="비유" text={entry.analogy} />
                <Detail label="다른 방법" text={entry.alternatives} />
                <Detail label="참고" text={entry.notes} />
              </li>
            )
          })}
        </ul>
      )}
    </section>
  )
}
