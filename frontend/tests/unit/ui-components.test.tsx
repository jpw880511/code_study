import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { Button } from '@/components/ui/button'
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card'
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

describe('cn', () => {
  it('keeps the last of two conflicting Tailwind classes', () => {
    const result = cn('px-2 py-1', 'px-4')
    expect(result.split(' ')).toContain('px-4')
    expect(result.split(' ')).toContain('py-1')
    expect(result.split(' ')).not.toContain('px-2')
  })

  it('drops falsy values and accepts arrays and objects', () => {
    const hidden = false as boolean
    const result = cn('a', hidden && 'b', undefined, null, ['c'], { d: true, e: false })
    expect(result.split(' ').sort()).toEqual(['a', 'c', 'd'])
  })
})

describe('Button', () => {
  it('renders and handles clicks', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>저장</Button>)
    await userEvent.click(screen.getByRole('button', { name: '저장' }))
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('does not click when disabled', async () => {
    const onClick = vi.fn()
    render(
      <Button disabled onClick={onClick}>
        저장
      </Button>,
    )
    await userEvent.click(screen.getByRole('button', { name: '저장' }))
    expect(onClick).not.toHaveBeenCalled()
  })

  it('exposes its variant and size', () => {
    render(
      <Button variant="destructive" size="lg">
        삭제
      </Button>,
    )
    const button = screen.getByRole('button', { name: '삭제' })
    expect(button).toHaveAttribute('data-variant', 'destructive')
    expect(button).toHaveAttribute('data-size', 'lg')
  })

  it('lets className override the default spacing', () => {
    render(<Button className="px-8">저장</Button>)
    const classes = screen.getByRole('button', { name: '저장' }).className.split(' ')
    expect(classes).toContain('px-8')
    expect(classes).not.toContain('px-2.5')
  })

  it('can render another element, such as a link, with the button styles', () => {
    render(
      <Button asChild>
        <a href="/trash">휴지통</a>
      </Button>,
    )
    const link = screen.getByRole('link', { name: '휴지통' })
    expect(link).toHaveAttribute('href', '/trash')
    expect(link).toHaveAttribute('data-slot', 'button')
  })
})

describe('Input, Label and Textarea', () => {
  it('lets the user type into an input', async () => {
    render(<Input aria-label="이메일" type="email" />)
    const input = screen.getByLabelText('이메일')
    await userEvent.type(input, 'student@example.com')
    expect(input).toHaveValue('student@example.com')
    expect(input).toHaveAttribute('type', 'email')
  })

  it('connects a label to its input', () => {
    render(
      <>
        <Label htmlFor="email">이메일</Label>
        <Input id="email" />
      </>,
    )
    expect(screen.getByLabelText('이메일')).toBeInTheDocument()
  })

  it('does not accept typing when disabled', async () => {
    render(<Input aria-label="이메일" disabled />)
    const input = screen.getByLabelText('이메일')
    await userEvent.type(input, 'abc')
    expect(input).toHaveValue('')
  })

  it('lets the user type into a textarea', async () => {
    render(<Textarea aria-label="설명" />)
    const textarea = screen.getByLabelText('설명')
    await userEvent.type(textarea, '첫 줄')
    expect(textarea).toHaveValue('첫 줄')
  })
})

describe('Card', () => {
  it('renders all its parts', () => {
    render(
      <Card>
        <CardHeader>
          <CardTitle>로그인</CardTitle>
          <CardDescription>계정 정보를 입력하세요</CardDescription>
        </CardHeader>
        <CardContent>본문</CardContent>
        <CardFooter>바닥글</CardFooter>
      </Card>,
    )
    for (const text of ['로그인', '계정 정보를 입력하세요', '본문', '바닥글']) {
      expect(screen.getByText(text)).toBeInTheDocument()
    }
  })
})

describe('Tabs', () => {
  function renderTabs() {
    return render(
      <Tabs defaultValue="document">
        <TabsList>
          <TabsTrigger value="document">Document</TabsTrigger>
          <TabsTrigger value="practice">Practice</TabsTrigger>
          <TabsTrigger value="qa">Q&A</TabsTrigger>
        </TabsList>
        <TabsContent value="document">교재 내용</TabsContent>
        <TabsContent value="practice">연습 문제</TabsContent>
        <TabsContent value="qa">질문과 답변</TabsContent>
      </Tabs>,
    )
  }

  it('shows the default tab only', () => {
    renderTabs()
    expect(screen.getByRole('tab', { name: 'Document' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByText('교재 내용')).toBeInTheDocument()
    expect(screen.queryByText('연습 문제')).not.toBeInTheDocument()
  })

  it('switches tabs on click', async () => {
    renderTabs()
    await userEvent.click(screen.getByRole('tab', { name: 'Practice' }))
    expect(screen.getByText('연습 문제')).toBeInTheDocument()
    expect(screen.queryByText('교재 내용')).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Practice' })).toHaveAttribute('aria-selected', 'true')
  })

  it('supports keyboard navigation between tabs', async () => {
    renderTabs()
    screen.getByRole('tab', { name: 'Document' }).focus()
    await userEvent.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Practice' })).toHaveFocus()
  })
})

describe('Dialog', () => {
  function renderDialog(onConfirm = vi.fn()) {
    render(
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="destructive">영구 삭제</Button>
        </DialogTrigger>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>정말 삭제할까요?</DialogTitle>
            <DialogDescription>이 작업은 되돌릴 수 없습니다.</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <DialogClose asChild>
              <Button variant="outline">취소</Button>
            </DialogClose>
            <Button onClick={onConfirm}>삭제</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>,
    )
    return onConfirm
  }

  it('is closed until the trigger is clicked', async () => {
    renderDialog()
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: '영구 삭제' }))

    const dialog = await screen.findByRole('dialog', { name: '정말 삭제할까요?' })
    expect(dialog).toHaveAccessibleDescription('이 작업은 되돌릴 수 없습니다.')
  })

  it('closes with the cancel button', async () => {
    renderDialog()
    await userEvent.click(screen.getByRole('button', { name: '영구 삭제' }))
    await screen.findByRole('dialog')

    await userEvent.click(screen.getByRole('button', { name: '취소' }))

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('closes with the Escape key', async () => {
    renderDialog()
    await userEvent.click(screen.getByRole('button', { name: '영구 삭제' }))
    await screen.findByRole('dialog')

    await userEvent.keyboard('{Escape}')

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })

  it('runs the confirm action', async () => {
    const onConfirm = renderDialog()
    await userEvent.click(screen.getByRole('button', { name: '영구 삭제' }))
    await userEvent.click(await screen.findByRole('button', { name: '삭제' }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })
})
