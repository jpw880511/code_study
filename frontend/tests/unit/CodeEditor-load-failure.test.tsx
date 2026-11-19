import { render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'

import { CodeEditor } from '../../src/components/document/CodeEditor'

vi.mock('../../src/components/document/MonacoEditor', () => {
  throw new Error('chunk load failed')
})

describe('CodeEditor when the editor chunk cannot be loaded', () => {
  it('shows an alert instead of crashing the page', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined)
    render(<CodeEditor code="x" language="python" label="코드" />)
    expect(await screen.findByRole('alert')).toHaveTextContent('코드 편집기를 불러오지 못했습니다.')
  })
})
