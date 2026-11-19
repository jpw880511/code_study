import { Component, lazy, Suspense, type ReactNode } from 'react'

export interface HighlightRequest {
  start: number
  end: number
  // Changes with every request, so asking for the same lines again scrolls there again.
  nonce: number
}

export interface CodeEditorProps {
  code: string
  // The language the server detected (e.g. "python"); unknown ones show as plain text.
  language: string
  // Accessible name of the editor.
  label: string
  // Lines to highlight and scroll to; null clears the highlight.
  highlight?: HighlightRequest | null
  // First visible line, reported when the user scrolls (not for scrolls this component caused).
  onTopLineChange?: (line: number) => void
}

// The one place that knows Monaco exists. The editor is a separate chunk that is loaded when
// the first code panel is shown, so it stays out of the main bundle. Tests replace this module.
const MonacoEditor = lazy(() => import('./MonacoEditor'))

// A chunk that fails to load (offline, stale deploy) must not take the whole page down.
class LoadFailureBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false }

  static getDerivedStateFromError() {
    return { failed: true }
  }

  render() {
    if (this.state.failed) {
      return (
        <p role="alert" className="p-4 text-destructive">
          코드 편집기를 불러오지 못했습니다. 페이지를 새로고침한 뒤 다시 시도하세요.
        </p>
      )
    }
    return this.props.children
  }
}

export function CodeEditor(props: CodeEditorProps) {
  return (
    <LoadFailureBoundary>
      <Suspense
        fallback={
          <p role="status" className="p-4 text-muted-foreground">
            코드 편집기를 불러오는 중...
          </p>
        }
      >
        <MonacoEditor {...props} />
      </Suspense>
    </LoadFailureBoundary>
  )
}
