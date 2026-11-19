import { useEffect, useRef, useState } from 'react'

import { cn } from '@/lib/utils'
import type { DocumentContent } from '../../services/document-service'
import Chapter1 from './chapters/Chapter1'
import Chapter2 from './chapters/Chapter2'
import Chapter3 from './chapters/Chapter3'
import Chapter4, { type ActiveEntry } from './chapters/Chapter4'
import Chapter5 from './chapters/Chapter5'
import Chapter6 from './chapters/Chapter6'
import Chapter7 from './chapters/Chapter7'

interface ExplanationPanelProps {
  content: DocumentContent
  // The chapter 4 entry that is current (chosen by the learner or followed from the code).
  activeEntry: ActiveEntry | null
  onSelectEntry: (index: number) => void
}

const CHAPTER_KEYS = [
  'chapter1',
  'chapter2',
  'chapter3',
  'chapter4',
  'chapter5',
  'chapter6',
  'chapter7',
] as const

// Chapter navigation (any chapter at any time) and the chapter being read.
export default function ExplanationPanel({
  content,
  activeEntry,
  onSelectEntry,
}: ExplanationPanelProps) {
  const [current, setCurrent] = useState(0)
  const region = useRef<HTMLDivElement>(null)

  // A new chapter starts at its top, not wherever the previous one was scrolled to.
  useEffect(() => {
    if (region.current) region.current.scrollTop = 0
  }, [current])

  return (
    <div className="grid h-full grid-rows-[auto_1fr] gap-3">
      <nav aria-label="챕터 탐색">
        <ol className="flex flex-wrap gap-1">
          {CHAPTER_KEYS.map((key, index) => (
            <li key={key}>
              <button
                type="button"
                aria-current={index === current ? 'true' : undefined}
                className={cn(
                  'rounded-md px-2 py-1 text-sm',
                  index === current ? 'bg-primary text-primary-foreground' : 'bg-muted',
                )}
                onClick={() => setCurrent(index)}
              >
                {`${index + 1}장 ${content[key].title}`}
              </button>
            </li>
          ))}
        </ol>
      </nav>
      <div
        ref={region}
        role="region"
        aria-label="챕터 내용"
        className="overflow-y-auto pr-1 lg:max-h-[75vh]"
      >
        {current === 0 && <Chapter1 chapter={content.chapter1} />}
        {current === 1 && <Chapter2 chapter={content.chapter2} />}
        {current === 2 && <Chapter3 chapter={content.chapter3} />}
        {current === 3 && (
          <Chapter4 chapter={content.chapter4} active={activeEntry} onSelect={onSelectEntry} />
        )}
        {current === 4 && <Chapter5 chapter={content.chapter5} />}
        {current === 5 && <Chapter6 chapter={content.chapter6} />}
        {current === 6 && <Chapter7 chapter={content.chapter7} />}
      </div>
    </div>
  )
}
