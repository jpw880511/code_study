import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import CodePanel from '../../src/components/document/CodePanel'
import { makeTaskCodeFile } from '../helpers/document-fixtures'

vi.mock('../../src/components/document/CodeEditor', () => import('../helpers/fake-code-editor'))

const calc = makeTaskCodeFile({ id: 'f-1', file_name: 'calc.py', content: 'calc 코드' })
const util = makeTaskCodeFile({
  id: 'f-2',
  file_name: 'util.py',
  file_path: 'src/util.py',
  content: 'util 코드',
})

describe('CodePanel', () => {
  it('shows a single file without tabs, with its name and language', () => {
    render(<CodePanel files={[calc]} highlight={null} />)
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.getByText('calc.py')).toBeInTheDocument()
    const editor = screen.getByTestId('code-editor')
    expect(editor).toHaveTextContent('calc 코드')
    expect(editor).toHaveAttribute('data-language', 'python')
    expect(screen.getByRole('group', { name: 'calc.py 코드' })).toBe(editor)
  })

  it('shows file tabs for several files (path first, else name) and switches on click', async () => {
    const user = userEvent.setup()
    render(<CodePanel files={[calc, util]} highlight={null} />)
    const tabs = screen.getAllByRole('tab')
    expect(tabs.map((t) => t.textContent)).toEqual(['calc.py', 'src/util.py'])
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    await user.click(tabs[1])
    expect(tabs[1]).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByTestId('code-editor')).toHaveTextContent('util 코드')
  })

  it('has an accessible tab list name', () => {
    render(<CodePanel files={[calc, util]} highlight={null} />)
    expect(screen.getByRole('tablist', { name: '코드 파일' })).toBeInTheDocument()
  })

  it('passes the highlight to the editor when the file is the one shown', () => {
    render(<CodePanel files={[calc]} highlight={{ file: 'calc.py', start: 2, end: 3, nonce: 7 }} />)
    expect(screen.getByTestId('code-editor')).toHaveAttribute('data-highlight', '2-3#7')
  })

  it('switches to the highlighted file (matched by path or by name) before highlighting', () => {
    const { rerender } = render(<CodePanel files={[calc, util]} highlight={null} />)
    rerender(
      <CodePanel
        files={[calc, util]}
        highlight={{ file: 'src/util.py', start: 1, end: 2, nonce: 1 }}
      />,
    )
    expect(screen.getByTestId('code-editor')).toHaveTextContent('util 코드')
    expect(screen.getByTestId('code-editor')).toHaveAttribute('data-highlight', '1-2#1')
    rerender(
      <CodePanel
        files={[calc, util]}
        highlight={{ file: 'calc.py', start: 3, end: 4, nonce: 2 }}
      />,
    )
    expect(screen.getByTestId('code-editor')).toHaveTextContent('calc 코드')
    rerender(
      <CodePanel
        files={[calc, util]}
        highlight={{ file: 'util.py', start: 5, end: 6, nonce: 3 }}
      />,
    )
    expect(screen.getByTestId('code-editor')).toHaveTextContent('util 코드')
  })

  it('lets the user switch tabs afterwards without the old highlight pulling back', async () => {
    const user = userEvent.setup()
    render(
      <CodePanel
        files={[calc, util]}
        highlight={{ file: 'src/util.py', start: 1, end: 2, nonce: 1 }}
      />,
    )
    await user.click(screen.getByRole('tab', { name: 'calc.py' }))
    expect(screen.getByTestId('code-editor')).toHaveTextContent('calc 코드')
    expect(screen.getByTestId('code-editor')).toHaveAttribute('data-highlight', '')
  })

  it('ignores a highlight for a file that is not in the code', () => {
    render(
      <CodePanel files={[calc]} highlight={{ file: 'missing.py', start: 1, end: 2, nonce: 1 }} />,
    )
    expect(screen.getByTestId('code-editor')).toHaveTextContent('calc 코드')
    expect(screen.getByTestId('code-editor')).toHaveAttribute('data-highlight', '')
  })

  it('reports the first visible line with the file being shown', async () => {
    const user = userEvent.setup()
    const onTopLineChange = vi.fn()
    render(<CodePanel files={[calc, util]} highlight={null} onTopLineChange={onTopLineChange} />)
    await user.click(screen.getByRole('button', { name: '4줄로 스크롤' }))
    expect(onTopLineChange).toHaveBeenCalledWith(calc, 4)
  })

  it('reports line 1 of the new file when the user switches tabs', async () => {
    const user = userEvent.setup()
    const onTopLineChange = vi.fn()
    render(<CodePanel files={[calc, util]} highlight={null} onTopLineChange={onTopLineChange} />)
    await user.click(screen.getByRole('tab', { name: 'src/util.py' }))
    expect(onTopLineChange).toHaveBeenCalledWith(util, 1)
  })

  it('says so when there is no code', () => {
    render(<CodePanel files={[]} highlight={null} />)
    expect(screen.getByText('표시할 코드가 없습니다.')).toBeInTheDocument()
    expect(screen.queryByTestId('code-editor')).not.toBeInTheDocument()
  })
})
