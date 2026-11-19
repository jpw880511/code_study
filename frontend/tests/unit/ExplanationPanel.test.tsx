import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import ExplanationPanel from '../../src/components/document/ExplanationPanel'
import { makeContent } from '../helpers/document-fixtures'

const content = makeContent()
const noop = () => undefined

function nav() {
  return screen.getByRole('navigation', { name: '챕터 탐색' })
}

describe('ExplanationPanel', () => {
  it('lists the seven chapters in order, with chapter 1 current at first', () => {
    render(<ExplanationPanel content={content} activeEntry={null} onSelectEntry={noop} />)
    const buttons = within(nav()).getAllByRole('button')
    expect(buttons.map((b) => b.textContent)).toEqual([
      '1장 이 코드가 하는 일',
      '2장 미리 알아야 할 지식',
      '3장 코드 구조 한눈에 보기',
      '4장 한 줄씩 설명',
      '5장 실행 흐름 따라가기',
      '6장 핵심 개념 정리',
      '7장 흔한 실수',
    ])
    expect(buttons[0]).toHaveAttribute('aria-current', 'true')
    expect(buttons.filter((b) => b.hasAttribute('aria-current'))).toHaveLength(1)
    expect(screen.getByText('두 수를 더하는 계산기입니다.')).toBeInTheDocument()
  })

  it('jumps straight to any chapter, in any order, and moves the current marker', async () => {
    const user = userEvent.setup()
    render(<ExplanationPanel content={content} activeEntry={null} onSelectEntry={noop} />)
    await user.click(within(nav()).getByRole('button', { name: /^6장/ }))
    expect(screen.getByRole('heading', { name: '핵심 개념 정리' })).toBeInTheDocument()
    expect(within(nav()).getByRole('button', { name: /^6장/ })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(within(nav()).getByRole('button', { name: /^1장/ })).not.toHaveAttribute('aria-current')
    await user.click(within(nav()).getByRole('button', { name: /^2장/ }))
    expect(screen.getByRole('heading', { name: '미리 알아야 할 지식' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: '핵심 개념 정리' })).not.toBeInTheDocument()
  })

  it.each([
    [1, '이 코드가 하는 일'],
    [2, '미리 알아야 할 지식'],
    [3, '코드 구조 한눈에 보기'],
    [4, '한 줄씩 설명'],
    [5, '실행 흐름 따라가기'],
    [6, '핵심 개념 정리'],
    [7, '흔한 실수'],
  ])('shows chapter %i', async (number, title) => {
    const user = userEvent.setup()
    render(<ExplanationPanel content={content} activeEntry={null} onSelectEntry={noop} />)
    await user.click(within(nav()).getByRole('button', { name: new RegExp(`^${number}장`) }))
    expect(screen.getByRole('heading', { level: 3, name: title })).toBeInTheDocument()
  })

  it('passes the active entry and the selection callback to chapter 4', async () => {
    const user = userEvent.setup()
    const onSelectEntry = vi.fn()
    render(
      <ExplanationPanel
        content={content}
        activeEntry={{ index: 1, source: 'code' }}
        onSelectEntry={onSelectEntry}
      />,
    )
    await user.click(within(nav()).getByRole('button', { name: /^4장/ }))
    expect(screen.getByRole('button', { name: 'calc.py 4~5줄 코드에서 보기' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    await user.click(screen.getByText('두 수를 더해 돌려줍니다.'))
    expect(onSelectEntry).toHaveBeenLastCalledWith(0)
  })

  it('shows the chapter in a labelled region that returns to the top when the chapter changes', async () => {
    const user = userEvent.setup()
    render(<ExplanationPanel content={content} activeEntry={null} onSelectEntry={noop} />)
    const region = screen.getByRole('region', { name: '챕터 내용' })
    // jsdom does not scroll; a plain writable property lets the reset be observed.
    Object.defineProperty(region, 'scrollTop', { value: 120, writable: true })
    await user.click(within(nav()).getByRole('button', { name: /^3장/ }))
    expect(region.scrollTop).toBe(0)
  })
})
