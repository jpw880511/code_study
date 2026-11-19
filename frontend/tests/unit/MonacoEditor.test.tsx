import { fireEvent, render, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import MonacoEditor from '../../src/components/document/MonacoEditor'

// A hand-made stand-in for the slice of the Monaco API that MonacoEditor uses: jsdom cannot
// run the real editor. It records calls so the wiring can be checked.
const fake = vi.hoisted(() => {
  class Editor {
    value: string
    scrollListener: (() => void) | null = null
    topLine = 1
    disposed = false
    options: Record<string, unknown>
    model = { id: 'model' }
    decorations: unknown[] = []
    constructor(options: Record<string, unknown>) {
      this.options = options
      this.value = String(options.value)
    }
    getValue() {
      return this.value
    }
    setValue(value: string) {
      this.value = value
    }
    getModel() {
      return this.model
    }
    onDidScrollChange(listener: () => void) {
      this.scrollListener = listener
      return { dispose: vi.fn() }
    }
    getVisibleRanges() {
      return [{ startLineNumber: this.topLine }]
    }
    // Like Monaco, an immediate programmatic reveal fires the scroll event synchronously.
    revealLineNearTop = vi.fn((line: number) => {
      this.topLine = line
      this.scrollListener?.()
    })
    setScrollTop = vi.fn((top: number) => {
      if (top === 0) this.topLine = 1
      this.scrollListener?.()
    })
    createDecorationsCollection = vi.fn(() => ({
      set: (items: unknown[]) => {
        this.decorations = items
      },
      clear: () => {
        this.decorations = []
      },
    }))
    dispose() {
      this.disposed = true
    }
    // The user scrolls.
    userScrollTo(line: number) {
      this.topLine = line
      this.scrollListener?.()
    }
  }
  const editors: Editor[] = []
  const monaco = {
    editor: {
      create: vi.fn((_el: HTMLElement, options: Record<string, unknown>) => {
        const editor = new Editor(options)
        editors.push(editor)
        return editor
      }),
      setModelLanguage: vi.fn(),
      ScrollType: { Immediate: 1 },
    },
    Range: class {
      startLineNumber: number
      startColumn: number
      endLineNumber: number
      endColumn: number
      constructor(startLine: number, startColumn: number, endLine: number, endColumn: number) {
        this.startLineNumber = startLine
        this.startColumn = startColumn
        this.endLineNumber = endLine
        this.endColumn = endColumn
      }
    },
  }
  return { monaco, editors }
})

vi.mock('../../src/components/document/monaco-runtime', () => ({
  monaco: fake.monaco,
  monacoLanguageId: (language: string) => (language === 'c++' ? 'cpp' : language),
}))

const last = () => fake.editors[fake.editors.length - 1]

beforeEach(() => {
  fake.editors.length = 0
  vi.clearAllMocks()
})

afterEach(() => {
  vi.useRealTimers()
})

describe('MonacoEditor', () => {
  it('creates a read-only editor with line numbers, the code and the language', () => {
    render(<MonacoEditor code={'a = 1\n'} language="python" label="calc.py 코드" />)
    const [, options] = fake.monaco.editor.create.mock.calls[0]
    expect(options).toMatchObject({
      value: 'a = 1\n',
      language: 'python',
      readOnly: true,
      lineNumbers: 'on',
      ariaLabel: 'calc.py 코드',
    })
  })

  it('maps the detected language to the Monaco language id', () => {
    render(<MonacoEditor code="x" language="c++" label="코드" />)
    expect(fake.monaco.editor.create.mock.calls[0][1]).toMatchObject({ language: 'cpp' })
  })

  it('swaps the content and language when the props change', () => {
    const { rerender } = render(<MonacoEditor code="a" language="python" label="코드" />)
    rerender(<MonacoEditor code="b" language="javascript" label="코드" />)
    expect(last().value).toBe('b')
    expect(fake.monaco.editor.setModelLanguage).toHaveBeenLastCalledWith(last().model, 'javascript')
    expect(fake.monaco.editor.create).toHaveBeenCalledTimes(1)
  })

  it('does not reset the content when it did not change', () => {
    const { rerender } = render(<MonacoEditor code="a" language="python" label="코드" />)
    const setValue = vi.spyOn(last(), 'setValue')
    rerender(<MonacoEditor code="a" language="python" label="다른 라벨" />)
    expect(setValue).not.toHaveBeenCalled()
  })

  it('highlights the whole lines of the range and scrolls to its first line', () => {
    const { rerender } = render(<MonacoEditor code="a" language="python" label="코드" />)
    expect(last().decorations).toEqual([])
    rerender(
      <MonacoEditor
        code="a"
        language="python"
        label="코드"
        highlight={{ start: 4, end: 6, nonce: 1 }}
      />,
    )
    expect(last().decorations).toEqual([
      {
        range: expect.objectContaining({ startLineNumber: 4, endLineNumber: 6 }),
        options: expect.objectContaining({ isWholeLine: true }),
      },
    ])
    expect(last().revealLineNearTop).toHaveBeenCalledWith(4, 1)
  })

  it('scrolls again when the same range is requested again (new nonce)', () => {
    const props = { code: 'a', language: 'python', label: '코드' }
    const { rerender } = render(
      <MonacoEditor {...props} highlight={{ start: 4, end: 6, nonce: 1 }} />,
    )
    rerender(<MonacoEditor {...props} highlight={{ start: 4, end: 6, nonce: 2 }} />)
    expect(last().revealLineNearTop).toHaveBeenCalledTimes(2)
  })

  it('removes the highlight when it becomes null', () => {
    const props = { code: 'a', language: 'python', label: '코드' }
    const { rerender } = render(
      <MonacoEditor {...props} highlight={{ start: 1, end: 2, nonce: 1 }} />,
    )
    rerender(<MonacoEditor {...props} highlight={null} />)
    expect(last().decorations).toEqual([])
  })

  it('reports the first visible line when a scroll follows the learner input', () => {
    const onTopLineChange = vi.fn()
    const { container } = render(
      <MonacoEditor code="a" language="python" label="코드" onTopLineChange={onTopLineChange} />,
    )
    fireEvent.wheel(container.firstChild as Element)
    last().userScrollTo(5)
    last().userScrollTo(9)
    expect(onTopLineChange.mock.calls).toEqual([[5], [9]])
  })

  it.each([
    ['touchstart', (el: Element) => fireEvent.touchStart(el)],
    ['touchmove', (el: Element) => fireEvent.touchMove(el)],
    ['keydown', (el: Element) => fireEvent.keyDown(el, { key: 'PageDown' })],
  ])('counts %s as the learner scrolling', (_name, input) => {
    const onTopLineChange = vi.fn()
    const { container } = render(
      <MonacoEditor code="a" language="python" label="코드" onTopLineChange={onTopLineChange} />,
    )
    input(container.firstChild as Element)
    last().userScrollTo(3)
    expect(onTopLineChange).toHaveBeenCalledWith(3)
  })

  it('counts dragging the scrollbar (pointer held down) until the pointer is released', () => {
    vi.useFakeTimers()
    const onTopLineChange = vi.fn()
    const { container } = render(
      <MonacoEditor code="a" language="python" label="코드" onTopLineChange={onTopLineChange} />,
    )
    fireEvent.pointerDown(container.firstChild as Element)
    vi.advanceTimersByTime(5000)
    last().userScrollTo(8)
    expect(onTopLineChange).toHaveBeenCalledWith(8)
    fireEvent.pointerUp(window)
    vi.advanceTimersByTime(5000)
    last().userScrollTo(9)
    expect(onTopLineChange).toHaveBeenCalledTimes(1)
  })

  it('does not report scrolls without learner input (its own scrolls and layout events)', () => {
    const onTopLineChange = vi.fn()
    const props = { code: 'a', language: 'python', label: '코드', onTopLineChange }
    const { rerender } = render(<MonacoEditor {...props} />)
    rerender(<MonacoEditor {...props} highlight={{ start: 7, end: 8, nonce: 1 }} />)
    expect(last().revealLineNearTop).toHaveBeenCalled()
    // A late event after the reveal (e.g. from a layout change) is not the learner's.
    last().userScrollTo(1)
    expect(onTopLineChange).not.toHaveBeenCalled()
  })

  it('stops counting input once the window has passed', () => {
    vi.useFakeTimers()
    const onTopLineChange = vi.fn()
    const { container } = render(
      <MonacoEditor code="a" language="python" label="코드" onTopLineChange={onTopLineChange} />,
    )
    fireEvent.wheel(container.firstChild as Element)
    vi.advanceTimersByTime(600)
    last().userScrollTo(4)
    expect(onTopLineChange).not.toHaveBeenCalled()
  })

  it('goes back to the top without reporting when another file is shown', () => {
    const onTopLineChange = vi.fn()
    const props = { language: 'python', label: '코드', onTopLineChange }
    const { rerender } = render(<MonacoEditor {...props} code="a" />)
    rerender(<MonacoEditor {...props} code="b" />)
    expect(last().setScrollTop).toHaveBeenCalledWith(0)
    expect(onTopLineChange).not.toHaveBeenCalled()
  })

  it('ignores scroll events with no visible range', () => {
    const onTopLineChange = vi.fn()
    const { container } = render(
      <MonacoEditor code="a" language="python" label="코드" onTopLineChange={onTopLineChange} />,
    )
    fireEvent.wheel(container.firstChild as Element)
    vi.spyOn(last(), 'getVisibleRanges').mockReturnValue([])
    last().scrollListener?.()
    expect(onTopLineChange).not.toHaveBeenCalled()
  })

  it('disposes the editor on unmount', async () => {
    const { unmount } = render(<MonacoEditor code="a" language="python" label="코드" />)
    const editor = last()
    unmount()
    await waitFor(() => expect(editor.disposed).toBe(true))
  })
})
