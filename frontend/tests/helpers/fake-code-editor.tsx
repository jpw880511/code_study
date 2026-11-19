import type { CodeEditorProps } from '../../src/components/document/CodeEditor'

// Stand-in for the lazily loaded Monaco editor in component tests (jsdom cannot run Monaco).
// It shows what it was given as plain text and has buttons that act like the user scrolling.
// Use it with: vi.mock('<path>/components/document/CodeEditor', () => import('<path>/helpers/fake-code-editor'))
export function CodeEditor({ code, language, label, highlight, onTopLineChange }: CodeEditorProps) {
  return (
    <div
      role="group"
      aria-label={label}
      data-testid="code-editor"
      data-language={language}
      data-highlight={highlight ? `${highlight.start}-${highlight.end}#${highlight.nonce}` : ''}
    >
      <pre>{code}</pre>
      {[1, 2, 3, 4, 5, 6].map((line) => (
        <button key={line} type="button" onClick={() => onTopLineChange?.(line)}>
          {`${line}줄로 스크롤`}
        </button>
      ))}
    </div>
  )
}
