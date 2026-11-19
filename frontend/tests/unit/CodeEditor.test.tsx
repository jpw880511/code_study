import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CodeEditor } from '../../src/components/document/CodeEditor'

// The real MonacoEditor pulls in Monaco, which jsdom cannot run; here it is a stub whose
// loading (or failing to load) is what the wrapper is tested on.
vi.mock('../../src/components/document/MonacoEditor', () => {
  return {
    default: ({ code, language }: { code: string; language: string }) => (
      <pre data-testid="monaco" data-language={language}>
        {code}
      </pre>
    ),
  }
})

describe('CodeEditor', () => {
  it('shows a loading status first, then the lazily loaded editor with the props', async () => {
    render(<CodeEditor code="print(1)" language="python" label="calc.py 코드" />)
    expect(screen.getByRole('status')).toHaveTextContent('코드 편집기를 불러오는 중')
    const editor = await screen.findByTestId('monaco')
    expect(editor).toHaveTextContent('print(1)')
    expect(editor).toHaveAttribute('data-language', 'python')
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })
})
