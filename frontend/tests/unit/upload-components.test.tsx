import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useState } from 'react'
import { describe, expect, it, vi } from 'vitest'

import FileUpload from '../../src/components/upload/FileUpload'
import FolderUpload from '../../src/components/upload/FolderUpload'
import PasteCode from '../../src/components/upload/PasteCode'
import type { FolderEntry } from '../../src/services/task-service'
import { makeFile } from '../helpers/task-fixtures'

function FileHarness({ initial = [] as File[], error }: { initial?: File[]; error?: string }) {
  const [files, setFiles] = useState(initial)
  return <FileUpload files={files} onChange={setFiles} error={error} />
}

describe('FileUpload', () => {
  it('has a labelled file input that accepts several files and is reachable by keyboard', () => {
    render(<FileHarness />)
    const input = screen.getByLabelText(/파일 선택/)
    expect(input).toHaveAttribute('type', 'file')
    expect(input).toHaveAttribute('multiple')
    expect(input).not.toHaveAttribute('tabindex', '-1')
    expect(screen.getByText(/끌어다 놓/)).toBeInTheDocument()
  })

  it('lists the chosen files with their sizes and appends later picks', async () => {
    const user = userEvent.setup()
    render(<FileHarness />)
    await user.upload(screen.getByLabelText(/파일 선택/), [makeFile('a.py'), makeFile('b.js')])
    await user.upload(screen.getByLabelText(/파일 선택/), makeFile('c.css'))
    const list = screen.getByRole('list', { name: '선택한 파일' })
    expect(
      within(list)
        .getAllByRole('listitem')
        .map((i) => i.textContent),
    ).toEqual([
      expect.stringContaining('a.py'),
      expect.stringContaining('b.js'),
      expect.stringContaining('c.css'),
    ])
    expect(within(list).getAllByText(/\d+(\.\d+)? (B|KB|MB)/)).toHaveLength(3)
  })

  it('ignores a file that was already chosen', async () => {
    const user = userEvent.setup()
    const file = makeFile('a.py')
    render(<FileHarness initial={[file]} />)
    await user.upload(screen.getByLabelText(/파일 선택/), file)
    expect(screen.getAllByRole('listitem')).toHaveLength(1)
  })

  it('removes a file with its own button', async () => {
    const user = userEvent.setup()
    render(<FileHarness initial={[makeFile('a.py'), makeFile('b.js')]} />)
    await user.click(screen.getByRole('button', { name: 'a.py 제거' }))
    expect(screen.queryByText('a.py')).not.toBeInTheDocument()
    expect(screen.getByText('b.js')).toBeInTheDocument()
  })

  it('accepts dropped files', () => {
    render(<FileHarness />)
    const zone = screen.getByTestId('file-drop-zone')
    fireEvent.dragOver(zone, { dataTransfer: { files: [] } })
    expect(zone).toHaveAttribute('data-dragging', 'true')
    fireEvent.dragLeave(zone)
    expect(zone).toHaveAttribute('data-dragging', 'false')
    fireEvent.dragOver(zone, { dataTransfer: { files: [] } })
    fireEvent.drop(zone, { dataTransfer: { files: [makeFile('dropped.py')] } })
    expect(screen.getByText('dropped.py')).toBeInTheDocument()
    expect(zone).toHaveAttribute('data-dragging', 'false')
  })

  it('renders file names as text, never as markup', () => {
    render(<FileHarness initial={[makeFile('<img src=x onerror=alert(1)>.py')]} />)
    expect(screen.getByText('<img src=x onerror=alert(1)>.py')).toBeInTheDocument()
    expect(document.querySelector('img')).toBeNull()
  })

  it('announces a validation error', () => {
    render(<FileHarness error="파일이 너무 많습니다." />)
    expect(screen.getByRole('alert')).toHaveTextContent('파일이 너무 많습니다.')
  })
})

function entry(path: string): FolderEntry {
  return { file: makeFile(path.split('/').pop()!, 'x', path), path }
}

function FolderHarness({
  initial = [] as FolderEntry[],
  excluded = [] as string[],
}: {
  initial?: FolderEntry[]
  excluded?: string[]
}) {
  const [state, setState] = useState({ entries: initial, excludedPaths: excluded })
  return <FolderUpload {...state} onChange={setState} />
}

describe('FolderUpload', () => {
  it('has a labelled directory input', () => {
    render(<FolderHarness />)
    const input = screen.getByLabelText(/폴더 선택/)
    expect(input).toHaveAttribute('webkitdirectory')
    expect(input).toHaveAttribute('multiple')
  })

  it('keeps relative paths and filters excluded ones before they are sent, with a notice', async () => {
    const user = userEvent.setup()
    render(<FolderHarness />)
    await user.upload(screen.getByLabelText(/폴더 선택/), [
      makeFile('App.jsx', 'x', 'my-app/src/App.jsx'),
      makeFile('index.js', 'x', 'my-app/node_modules/a/index.js'),
      makeFile('config', 'x', 'my-app/.git/config'),
    ])
    const list = screen.getByRole('list', { name: '선택한 폴더 파일' })
    expect(within(list).getAllByRole('listitem')).toHaveLength(1)
    expect(within(list).getByText('my-app/src/App.jsx')).toBeInTheDocument()
    expect(screen.getByRole('status')).toHaveTextContent(
      '일반적인 빌드/시스템 폴더를 제외했습니다: .git, node_modules, __pycache__',
    )
    expect(screen.getByRole('status')).toHaveTextContent('2개')
  })

  it('shows no notice when nothing was excluded', async () => {
    const user = userEvent.setup()
    render(<FolderHarness />)
    await user.upload(screen.getByLabelText(/폴더 선택/), makeFile('a.py', 'x', 'app/a.py'))
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('replaces the previous selection when another folder is picked', async () => {
    const user = userEvent.setup()
    render(<FolderHarness initial={[entry('old/a.py')]} excluded={['old/.git/x']} />)
    await user.upload(screen.getByLabelText(/폴더 선택/), makeFile('b.py', 'x', 'new/b.py'))
    expect(screen.queryByText('old/a.py')).not.toBeInTheDocument()
    expect(screen.getByText('new/b.py')).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('announces a validation error', () => {
    render(
      <FolderUpload
        entries={[]}
        excludedPaths={[]}
        onChange={vi.fn()}
        error="폴더가 비었습니다."
      />,
    )
    expect(screen.getByRole('alert')).toHaveTextContent('폴더가 비었습니다.')
  })
})

function PasteHarness({ error }: { error?: string }) {
  const [value, setValue] = useState({ code: '', language: '' })
  return <PasteCode {...value} onChange={setValue} error={error} />
}

describe('PasteCode', () => {
  it('has a code textarea and a language dropdown starting at the placeholder', () => {
    render(<PasteHarness />)
    expect(screen.getByLabelText('코드')).toBeInstanceOf(HTMLTextAreaElement)
    const select = screen.getByLabelText('프로그래밍 언어')
    expect(select).toHaveValue('')
    const options = within(select).getAllByRole('option')
    expect(options[0]).toHaveTextContent('언어를 선택하세요')
    expect(options.slice(1).map((o) => (o as HTMLOptionElement).value)).toEqual([
      'python',
      'javascript',
      'typescript',
      'java',
      'c',
      'cpp',
      'html',
      'css',
      'markdown',
      'text',
    ])
    expect(within(select).getByRole('option', { name: 'C++' })).toHaveValue('cpp')
  })

  it('reports typed code and the chosen language', async () => {
    const user = userEvent.setup()
    render(<PasteHarness />)
    await user.type(screen.getByLabelText('코드'), 'print(1)')
    await user.selectOptions(screen.getByLabelText('프로그래밍 언어'), 'python')
    expect(screen.getByLabelText('코드')).toHaveValue('print(1)')
    expect(screen.getByLabelText('프로그래밍 언어')).toHaveValue('python')
  })

  it('announces a validation error', () => {
    render(<PasteHarness error="업로드하기 전에 프로그래밍 언어를 선택하세요." />)
    expect(screen.getByRole('alert')).toHaveTextContent(
      '업로드하기 전에 프로그래밍 언어를 선택하세요.',
    )
  })
})
