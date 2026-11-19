import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import DocumentStatusView from '../../src/components/document/DocumentStatusView'
import { makeStatus } from '../helpers/document-fixtures'

describe('DocumentStatusView', () => {
  it('says there is no document yet when the task has none', () => {
    render(<DocumentStatusView info={null} />)
    expect(screen.getByText('아직 학습 문서가 없습니다.')).toBeInTheDocument()
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('waits for the queue while pending', () => {
    render(
      <DocumentStatusView info={makeStatus({ status: 'pending', estimated_total_seconds: 20 })} />,
    )
    expect(screen.getByRole('status')).toHaveTextContent('문서 생성을 기다리는 중')
    expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  })

  it('shows the notice while pending too', () => {
    render(
      <DocumentStatusView
        info={makeStatus({ status: 'pending', notice: '대기열에 사람이 많습니다.' })}
      />,
    )
    expect(screen.getByText('대기열에 사람이 많습니다.')).toBeInTheDocument()
  })

  it('shows a progress bar with value attributes and the remaining time while in progress', () => {
    render(
      <DocumentStatusView
        info={makeStatus({
          status: 'in_progress',
          elapsed_seconds: 5,
          estimated_total_seconds: 20,
        })}
      />,
    )
    const bar = screen.getByRole('progressbar', { name: '문서 생성 진행률' })
    expect(bar).toHaveAttribute('aria-valuemin', '0')
    expect(bar).toHaveAttribute('aria-valuemax', '100')
    expect(bar).toHaveAttribute('aria-valuenow', '25')
    expect(screen.getByText('약 15초 남음')).toBeInTheDocument()
    expect(screen.getByText('문서를 만드는 중입니다.')).toBeInTheDocument()
  })

  it('never shows negative time: past the estimate it says it is almost done', () => {
    render(
      <DocumentStatusView
        info={makeStatus({
          status: 'in_progress',
          elapsed_seconds: 35,
          estimated_total_seconds: 20,
        })}
      />,
    )
    expect(screen.getByText('곧 완료됩니다')).toBeInTheDocument()
    expect(screen.queryByText(/남음/)).not.toBeInTheDocument()
    expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '99')
  })

  it('says "곧 완료됩니다" when exactly zero seconds remain', () => {
    render(
      <DocumentStatusView
        info={makeStatus({
          status: 'in_progress',
          elapsed_seconds: 20,
          estimated_total_seconds: 20,
        })}
      />,
    )
    expect(screen.getByText('곧 완료됩니다')).toBeInTheDocument()
  })

  it('has no value or time when the server sent no times', () => {
    render(<DocumentStatusView info={makeStatus({ status: 'in_progress' })} />)
    const bar = screen.getByRole('progressbar')
    expect(bar).not.toHaveAttribute('aria-valuenow')
    expect(screen.queryByText(/남음|곧 완료/)).not.toBeInTheDocument()
  })

  it('shows the retry notice while in progress', () => {
    render(
      <DocumentStatusView
        info={makeStatus({
          status: 'in_progress',
          elapsed_seconds: 1,
          estimated_total_seconds: 20,
          notice: 'AI 서비스가 바빠 다시 시도하는 중입니다 (1/3).',
        })}
      />,
    )
    expect(screen.getByText('AI 서비스가 바빠 다시 시도하는 중입니다 (1/3).')).toBeInTheDocument()
  })

  it('shows the server error as an alert when failed, with no restart button', () => {
    render(
      <DocumentStatusView
        info={makeStatus({
          status: 'failed',
          error: '문서를 만들지 못했습니다. 잠시 후 확인하세요.',
        })}
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent(
      '문서를 만들지 못했습니다. 잠시 후 확인하세요.',
    )
    expect(screen.queryByRole('button')).not.toBeInTheDocument()
  })

  it('falls back to a generic message when failed without an error text', () => {
    render(<DocumentStatusView info={makeStatus({ status: 'failed', error: null })} />)
    expect(screen.getByRole('alert')).toHaveTextContent('문서를 만들지 못했습니다.')
  })
})
