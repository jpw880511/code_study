import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import Chapter1 from '../../src/components/document/chapters/Chapter1'
import Chapter2 from '../../src/components/document/chapters/Chapter2'
import Chapter3 from '../../src/components/document/chapters/Chapter3'
import Chapter4 from '../../src/components/document/chapters/Chapter4'
import Chapter5 from '../../src/components/document/chapters/Chapter5'
import Chapter6 from '../../src/components/document/chapters/Chapter6'
import Chapter7 from '../../src/components/document/chapters/Chapter7'
import { makeContent } from '../helpers/document-fixtures'

const content = makeContent()

describe('Chapter1', () => {
  it('shows the title as a heading and the summary', () => {
    render(<Chapter1 chapter={content.chapter1} />)
    expect(screen.getByRole('heading', { name: '이 코드가 하는 일' })).toBeInTheDocument()
    expect(screen.getByText('두 수를 더하는 계산기입니다.')).toBeInTheDocument()
  })

  it('shows markup in the text as plain text, never as HTML', () => {
    const summary = '<div id="x">조심</div> <script>alert(1)</script> a < b'
    const { container } = render(<Chapter1 chapter={{ title: '제목', summary }} />)
    expect(screen.getByText(summary)).toBeInTheDocument()
    expect(container.querySelector('#x, script')).toBeNull()
  })
})

describe('Chapter2', () => {
  it('shows each concept as a card with its explanation, analogy, example and use cases', () => {
    render(<Chapter2 chapter={content.chapter2} />)
    expect(screen.getByRole('heading', { name: '미리 알아야 할 지식' })).toBeInTheDocument()
    const card = screen.getByRole('listitem', { name: '함수' })
    expect(within(card).getByText('이름을 붙인 코드 묶음입니다.')).toBeInTheDocument()
    expect(within(card).getByText('요리 레시피와 같습니다.')).toBeInTheDocument()
    expect(within(card).getByText('비유')).toBeInTheDocument()
    expect(within(card).getByText('def add(a, b): return a + b')).toBeInTheDocument()
    expect(within(card).getByText('활용 예')).toBeInTheDocument()
    expect(
      within(card).getByText('반복 작업을 줄이고, 같은 코드를 다시 쓸 때 사용합니다.'),
    ).toBeInTheDocument()
  })

  it('takes use_cases as the text the server sends, not as a list (it crashed the page once)', () => {
    // The structure's use_cases is one string. Treating it as an array threw "map is not a
    // function" in a real browser and blanked the whole page.
    const concept = { ...content.chapter2.concepts[0], use_cases: '첫째 줄\n둘째 줄' }
    const { container } = render(<Chapter2 chapter={{ title: '제목', concepts: [concept] }} />)
    expect(container.textContent).toContain('첫째 줄\n둘째 줄')
  })

  it('shows at most five cards', () => {
    const concept = content.chapter2.concepts[0]
    const concepts = Array.from({ length: 7 }, (_, i) => ({ ...concept, name: `개념 ${i + 1}` }))
    render(<Chapter2 chapter={{ title: '제목', concepts }} />)
    expect(screen.getAllByRole('heading', { level: 4 })).toHaveLength(5)
  })
})

describe('Chapter3', () => {
  it('shows the flowchart as fixed-width text and the files with their descriptions', () => {
    render(<Chapter3 chapter={content.chapter3} />)
    expect(screen.getByRole('heading', { name: '코드 구조 한눈에 보기' })).toBeInTheDocument()
    const flow = screen.getByLabelText('순서도')
    expect(flow.tagName).toBe('PRE')
    expect(flow).toHaveTextContent('main -> add -> 출력')
    expect(screen.getByText('calc.py')).toBeInTheDocument()
    expect(screen.getByText('계산 함수를 모아 둔 파일')).toBeInTheDocument()
  })

  it('keeps flowchart characters like < and > as text', () => {
    const flowchart = '<start> --> [x < 3]'
    render(<Chapter3 chapter={{ title: '제목', flowchart, file_breakdown: {} }} />)
    expect(screen.getByLabelText('순서도').textContent).toBe(flowchart)
  })
})

describe('Chapter4', () => {
  const noop = () => undefined

  it('lists every explanation with its file, line range, code and optional parts', () => {
    render(<Chapter4 chapter={content.chapter4} active={null} onSelect={noop} />)
    expect(screen.getByRole('heading', { name: '한 줄씩 설명' })).toBeInTheDocument()
    const first = screen.getByRole('listitem', { name: 'calc.py 1~2줄' })
    expect(within(first).getByText('두 수를 더해 돌려줍니다.')).toBeInTheDocument()
    expect(within(first).getByText(/def add\(a, b\):/)).toBeInTheDocument()
    expect(within(first).getByText('def 는 함수를 정의합니다.')).toBeInTheDocument()
    expect(within(first).getByText('계산기의 더하기 버튼')).toBeInTheDocument()
    expect(within(first).getByText('sum([a, b]) 도 가능합니다.')).toBeInTheDocument()
    // Empty optional fields and their labels are not shown.
    const second = screen.getByRole('listitem', { name: 'calc.py 4~5줄' })
    expect(within(second).queryByText('문법 분석')).not.toBeInTheDocument()
    expect(within(second).queryByText('비유')).not.toBeInTheDocument()
    expect(within(first).queryByText('참고')).not.toBeInTheDocument()
  })

  it('shows a single line as "N줄"', () => {
    const chapter = {
      title: '제목',
      explanations: [{ ...content.chapter4.explanations[0], line_start: 7, line_end: 7 }],
    }
    render(<Chapter4 chapter={chapter} active={null} onSelect={noop} />)
    expect(screen.getByRole('listitem', { name: 'calc.py 7줄' })).toBeInTheDocument()
  })

  it('selects an entry on click and on focus', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<Chapter4 chapter={content.chapter4} active={null} onSelect={onSelect} />)
    await user.click(
      within(screen.getByRole('listitem', { name: 'calc.py 4~5줄' })).getByText(
        '결과를 화면에 출력합니다.',
      ),
    )
    expect(onSelect).toHaveBeenLastCalledWith(1)
    onSelect.mockClear()
    screen.getByRole('button', { name: 'calc.py 1~2줄 코드에서 보기' }).focus()
    expect(onSelect).toHaveBeenCalledWith(0)
  })

  it('marks the active entry with aria-current and no other', () => {
    render(
      <Chapter4 chapter={content.chapter4} active={{ index: 1, source: 'user' }} onSelect={noop} />,
    )
    expect(screen.getByRole('button', { name: 'calc.py 4~5줄 코드에서 보기' })).toHaveAttribute(
      'aria-current',
      'true',
    )
    expect(screen.getByRole('button', { name: 'calc.py 1~2줄 코드에서 보기' })).not.toHaveAttribute(
      'aria-current',
    )
  })

  it('scrolls the active entry into view when the code panel moved it, not when the user chose it', () => {
    const scrollIntoView = vi.fn()
    Element.prototype.scrollIntoView = scrollIntoView
    const { rerender } = render(
      <Chapter4 chapter={content.chapter4} active={{ index: 1, source: 'user' }} onSelect={noop} />,
    )
    expect(scrollIntoView).not.toHaveBeenCalled()
    rerender(
      <Chapter4 chapter={content.chapter4} active={{ index: 0, source: 'code' }} onSelect={noop} />,
    )
    expect(scrollIntoView).toHaveBeenCalledTimes(1)
    expect(scrollIntoView.mock.contexts[0]).toBe(
      screen.getByRole('listitem', { name: 'calc.py 1~2줄' }),
    )
    // @ts-expect-error cleanup of the jsdom gap filled above
    delete Element.prototype.scrollIntoView
  })

  it('works when scrollIntoView does not exist and when no entry is active', () => {
    expect(() =>
      render(
        <Chapter4
          chapter={content.chapter4}
          active={{ index: 0, source: 'code' }}
          onSelect={noop}
        />,
      ),
    ).not.toThrow()
  })

  it('says so when there are no explanations', () => {
    render(<Chapter4 chapter={{ title: '제목', explanations: [] }} active={null} onSelect={noop} />)
    expect(screen.getByText('줄별 설명이 없습니다.')).toBeInTheDocument()
  })

  it('shows code and markup as plain text', () => {
    const entry = {
      ...content.chapter4.explanations[0],
      code: '<div onclick="x()">a < b</div>',
      what_it_does: '<b>굵게</b>',
    }
    const { container } = render(
      <Chapter4 chapter={{ title: '제목', explanations: [entry] }} active={null} onSelect={noop} />,
    )
    expect(screen.getByText('<div onclick="x()">a < b</div>')).toBeInTheDocument()
    expect(screen.getByText('<b>굵게</b>')).toBeInTheDocument()
    expect(container.querySelector('div[onclick], b')).toBeNull()
  })
})

describe('Chapter5', () => {
  it('lists the steps in order with their data', () => {
    render(<Chapter5 chapter={content.chapter5} />)
    expect(screen.getByRole('heading', { name: '실행 흐름 따라가기' })).toBeInTheDocument()
    const steps = screen.getAllByRole('listitem')
    expect(steps).toHaveLength(2)
    expect(steps[0]).toHaveTextContent('1단계')
    expect(steps[0]).toHaveTextContent('add 함수를 호출합니다.')
    expect(steps[0]).toHaveTextContent('a=1, b=2')
    expect(steps[1]).toHaveTextContent('2단계')
    expect(within(steps[1]).queryByText('데이터')).not.toBeInTheDocument()
  })
})

describe('Chapter6', () => {
  it('shows each concept with what, why and where', () => {
    render(<Chapter6 chapter={content.chapter6} />)
    expect(screen.getByRole('heading', { name: '핵심 개념 정리' })).toBeInTheDocument()
    const card = screen.getByRole('listitem', { name: '반환값' })
    expect(within(card).getByText('함수가 돌려주는 값')).toBeInTheDocument()
    expect(within(card).getByText('결과를 다른 곳에서 쓰려고')).toBeInTheDocument()
    expect(within(card).getByText('add 함수의 return')).toBeInTheDocument()
  })
})

describe('Chapter7', () => {
  it('shows each mistake with the wrong and right version, the reason and the fix', () => {
    render(<Chapter7 chapter={content.chapter7} />)
    expect(screen.getByRole('heading', { name: '흔한 실수' })).toBeInTheDocument()
    const item = screen.getByRole('listitem', { name: /실수 1/ })
    expect(within(item).getByText('return 을 빼먹기')).toBeInTheDocument()
    expect(within(item).getByText('return a + b')).toBeInTheDocument()
    expect(within(item).getByText('값이 None 이 됩니다.')).toBeInTheDocument()
    expect(within(item).getByText('return 을 추가하세요.')).toBeInTheDocument()
  })
})
