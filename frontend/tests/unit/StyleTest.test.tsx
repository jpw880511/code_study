import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { AppRoutes } from '../../src/App'
import {
  ResponsiveGridTest,
  ShadcnButtonTest,
  TailwindClassTest,
} from '../../src/components/dev/StyleTest'

describe('TailwindClassTest', () => {
  it('shows a sample styled with the four classes', () => {
    render(<TailwindClassTest />)
    const sample = screen.getByTestId('tailwind-sample')
    expect(sample.className.split(' ').sort()).toEqual(
      ['bg-blue-500', 'p-4', 'rounded-lg', 'text-white'].sort(),
    )
  })

  it.each([
    ['bg-blue-500', /배경색.*파란색/],
    ['text-white', /글자색.*흰색/],
    ['p-4', /안쪽 여백.*1rem/],
    ['rounded-lg', /모서리.*둥글/],
  ])('explains what %s does', (className, description) => {
    render(<TailwindClassTest />)
    const item = screen.getByText(className, { selector: 'code' }).closest('li')
    expect(item).not.toBeNull()
    expect(within(item as HTMLElement).getByText(description)).toBeInTheDocument()
  })

  it('states the real values used by this project theme', () => {
    render(<TailwindClassTest />)
    expect(screen.getByText(/oklch\(62\.3% 0\.214 259\.815\)/)).toBeInTheDocument()
    expect(screen.getByText(/16px/)).toBeInTheDocument()
    expect(screen.getByText(/0\.625rem/)).toBeInTheDocument()
  })

  it('does not use the misspelled class that Tailwind would ignore', () => {
    render(<TailwindClassTest />)
    expect(screen.queryByText('bg-bue-500')).not.toBeInTheDocument()
  })
})

describe('ShadcnButtonTest', () => {
  const alertMock = vi.fn()

  beforeEach(() => {
    alertMock.mockReset()
    vi.spyOn(window, 'alert').mockImplementation(alertMock)
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('renders three buttons with the default, outline and ghost variants', () => {
    render(<ShadcnButtonTest />)
    const buttons = screen.getAllByRole('button')
    expect(buttons.map((button) => button.textContent)).toEqual(['default', 'outline', 'ghost'])
    expect(buttons.map((button) => button.getAttribute('data-variant'))).toEqual([
      'default',
      'outline',
      'ghost',
    ])
  })

  it('does not show an alert until a button is clicked', () => {
    render(<ShadcnButtonTest />)
    expect(alertMock).not.toHaveBeenCalled()
  })

  it.each(['default', 'outline', 'ghost'])(
    'shows an alert with the variant name when the %s button is clicked',
    async (variant) => {
      render(<ShadcnButtonTest />)
      await userEvent.click(screen.getByRole('button', { name: variant }))
      expect(alertMock).toHaveBeenCalledTimes(1)
      expect(alertMock).toHaveBeenCalledWith(variant)
    },
  )

  it('shows one alert per click', async () => {
    render(<ShadcnButtonTest />)
    await userEvent.click(screen.getByRole('button', { name: 'outline' }))
    await userEvent.click(screen.getByRole('button', { name: 'ghost' }))
    expect(alertMock.mock.calls).toEqual([['outline'], ['ghost']])
  })
})

describe('ResponsiveGridTest', () => {
  it('lays out three cards in a grid', () => {
    render(<ResponsiveGridTest />)
    const grid = screen.getByTestId('responsive-grid')
    expect(within(grid).getAllByRole('article')).toHaveLength(3)
    expect(within(grid).getByText('카드 1')).toBeInTheDocument()
    expect(within(grid).getByText('카드 2')).toBeInTheDocument()
    expect(within(grid).getByText('카드 3')).toBeInTheDocument()
  })

  it('uses 1 column by default, 2 from md and 3 from lg', () => {
    render(<ResponsiveGridTest />)
    const classes = screen.getByTestId('responsive-grid').className.split(' ')
    expect(classes).toEqual(
      expect.arrayContaining(['grid', 'grid-cols-1', 'md:grid-cols-2', 'lg:grid-cols-3']),
    )
  })

  it('explains the breakpoints in text', () => {
    render(<ResponsiveGridTest />)
    expect(screen.getByText(/모바일.*1열/)).toBeInTheDocument()
    expect(screen.getByText(/태블릿.*md.*768px.*2열/)).toBeInTheDocument()
    expect(screen.getByText(/데스크톱.*lg.*1024px.*3열/)).toBeInTheDocument()
  })
})

describe('/dev-test route', () => {
  it('has the three new sections below the existing tests', () => {
    render(
      <MemoryRouter initialEntries={['/dev-test']}>
        <AppRoutes />
      </MemoryRouter>,
    )
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent)
    expect(headings).toEqual([
      'Zustand 인증 스토어 테스트',
      'Tailwind 클래스 테스트',
      'shadcn/ui 버튼 테스트',
      '반응형 디자인 테스트',
    ])
    expect(screen.getByRole('heading', { level: 1, name: 'API 테스트' })).toBeInTheDocument()
  })
})
