import { useEffect, useRef } from 'react'

import type { CodeEditorProps } from './CodeEditor'
import { monaco, monacoLanguageId } from './monaco-runtime'

type StandaloneEditor = ReturnType<typeof monaco.editor.create>
type TextModel = NonNullable<ReturnType<StandaloneEditor['getModel']>>

// A scroll counts as the learner's only if their input (wheel, touch, keys, scrollbar) came
// just before it. Scrolls this component causes (showing another file, revealing lines) and
// the layout events that follow them arrive without such input, so they are never reported
// back and the two panels cannot chase each other.
const USER_SCROLL_WINDOW_MS = 500

// The real editor, behind CodeEditor's lazy boundary. Nothing else imports Monaco.
export default function MonacoEditor({
  code,
  language,
  label,
  highlight = null,
  onTopLineChange,
}: CodeEditorProps) {
  const container = useRef<HTMLDivElement>(null)
  const editorRef = useRef<StandaloneEditor | null>(null)
  const decorations = useRef<ReturnType<StandaloneEditor['createDecorationsCollection']> | null>(
    null,
  )
  const lastInput = useRef(Number.NEGATIVE_INFINITY)
  const pointerDown = useRef(false)
  const onTopLine = useRef(onTopLineChange)
  const initial = useRef({ code, language, label })

  useEffect(() => {
    onTopLine.current = onTopLineChange
  }, [onTopLineChange])

  useEffect(() => {
    const element = container.current as HTMLDivElement
    const { code: value, language: lang, label: ariaLabel } = initial.current
    const editor = monaco.editor.create(element, {
      value,
      language: monacoLanguageId(lang),
      readOnly: true,
      lineNumbers: 'on',
      ariaLabel,
      automaticLayout: true,
      minimap: { enabled: false },
      scrollBeyondLastLine: false,
      fontSize: 13,
    })
    editorRef.current = editor
    decorations.current = editor.createDecorationsCollection()

    const markInput = () => {
      lastInput.current = performance.now()
    }
    const pressPointer = () => {
      pointerDown.current = true
      markInput()
    }
    const releasePointer = () => {
      pointerDown.current = false
    }
    const inputEvents = ['wheel', 'touchstart', 'touchmove', 'keydown'] as const
    inputEvents.forEach((name) => element.addEventListener(name, markInput, true))
    element.addEventListener('pointerdown', pressPointer, true)
    window.addEventListener('pointerup', releasePointer)

    const subscription = editor.onDidScrollChange(() => {
      const fromUser =
        pointerDown.current || performance.now() - lastInput.current < USER_SCROLL_WINDOW_MS
      if (!fromUser) return
      const line = editor.getVisibleRanges()[0]?.startLineNumber
      if (line !== undefined) onTopLine.current?.(line)
    })

    return () => {
      subscription.dispose()
      inputEvents.forEach((name) => element.removeEventListener(name, markInput, true))
      element.removeEventListener('pointerdown', pressPointer, true)
      window.removeEventListener('pointerup', releasePointer)
      editor.dispose()
      editorRef.current = null
    }
  }, [])

  useEffect(() => {
    // The editor is created by the effect above, which runs first.
    const editor = editorRef.current as StandaloneEditor
    if (editor.getValue() === code) return
    editor.setValue(code)
    editor.setScrollTop(0)
  }, [code])

  useEffect(() => {
    const model = (editorRef.current as StandaloneEditor).getModel() as TextModel
    monaco.editor.setModelLanguage(model, monacoLanguageId(language))
  }, [language])

  // The dependency is the whole request: a new nonce asks for the same lines again.
  useEffect(() => {
    const editor = editorRef.current as StandaloneEditor
    const marks = decorations.current as ReturnType<StandaloneEditor['createDecorationsCollection']>
    if (!highlight) {
      marks.clear()
      return
    }
    marks.set([
      {
        range: new monaco.Range(highlight.start, 1, highlight.end, 1),
        options: { isWholeLine: true, className: 'code-highlight-line' },
      },
    ])
    editor.revealLineNearTop(highlight.start, monaco.editor.ScrollType.Immediate)
  }, [highlight])

  return <div ref={container} className="h-full min-h-64 w-full" />
}
