import { describe, expect, it } from 'vitest'

import {
  createTask,
  deleteTask,
  getTask,
  getTaskCode,
  listTasks,
  updateTask,
} from '../../src/services/task-service'
import { isApiError } from '../../src/services/api-client'
import { errorBody, mockApi, reply, requestKey } from '../helpers/mock-api'
import { makeCreateResult, makeFile, makeTask, makeTaskDetail } from '../helpers/task-fixtures'

const adapter = mockApi()

function lastConfig() {
  return adapter.mock.calls.at(-1)![0]
}

describe('read and write endpoints', () => {
  it('listTasks GETs /projects/:id/tasks and returns the bare array', async () => {
    const tasks = [makeTask()]
    adapter.mockImplementation(async (c) => reply(c, 200, tasks))
    await expect(listTasks('p-1')).resolves.toEqual(tasks)
    expect(requestKey(lastConfig())).toBe('GET /projects/p-1/tasks')
  })

  it('getTask GETs /tasks/:id', async () => {
    const detail = makeTaskDetail()
    adapter.mockImplementation(async (c) => reply(c, 200, detail))
    await expect(getTask('t-1')).resolves.toEqual(detail)
    expect(requestKey(lastConfig())).toBe('GET /tasks/t-1')
  })

  it('updateTask PATCHes only the given fields', async () => {
    adapter.mockImplementation(async (c) => reply(c, 200, makeTask()))
    await updateTask('t-1', { description: null })
    expect(requestKey(lastConfig())).toBe('PATCH /tasks/t-1')
    expect(JSON.parse(lastConfig().data)).toEqual({ description: null })
  })

  it('deleteTask DELETEs /tasks/:id', async () => {
    adapter.mockImplementation(async (c) => reply(c, 204))
    await expect(deleteTask('t-1')).resolves.toBeUndefined()
    expect(requestKey(lastConfig())).toBe('DELETE /tasks/t-1')
  })

  it('getTaskCode GETs /tasks/:id/code', async () => {
    const code = { files: [] }
    adapter.mockImplementation(async (c) => reply(c, 200, code))
    await expect(getTaskCode('t-1')).resolves.toEqual(code)
    expect(requestKey(lastConfig())).toBe('GET /tasks/t-1/code')
  })
})

describe('createTask', () => {
  function answer() {
    adapter.mockImplementation(async (c) => reply(c, 201, makeCreateResult()))
  }
  function sent() {
    const { data } = lastConfig()
    expect(data).toBeInstanceOf(FormData)
    return data as FormData
  }

  it('sends files as repeated parts and never sets Content-Type itself', async () => {
    answer()
    const a = makeFile('a.py')
    const b = makeFile('b.js')
    await createTask('p-1', {
      title: '제목입니다',
      description: '설명',
      upload: { method: 'file', files: [a, b] },
    })
    expect(requestKey(lastConfig())).toBe('POST /projects/p-1/tasks')
    const form = sent()
    expect(form.get('title')).toBe('제목입니다')
    expect(form.get('description')).toBe('설명')
    expect(form.get('upload_method')).toBe('file')
    expect(form.getAll('files')).toEqual([a, b])
    expect(form.has('paths')).toBe(false)
    expect(String(lastConfig().headers.get('Content-Type') ?? '')).not.toContain('multipart')
  })

  it('omits description when it is empty', async () => {
    answer()
    await createTask('p-1', {
      title: '제목입니다',
      upload: { method: 'file', files: [makeFile('a.py')] },
    })
    expect(sent().has('description')).toBe(false)
  })

  it('sends folder files with paths in the same order', async () => {
    answer()
    const a = makeFile('a.py')
    const b = makeFile('b.py')
    await createTask('p-1', {
      title: '제목입니다',
      upload: {
        method: 'folder',
        entries: [
          { file: a, path: 'app/a.py' },
          { file: b, path: 'app/src/b.py' },
        ],
      },
    })
    const form = sent()
    expect(form.get('upload_method')).toBe('folder')
    expect(form.getAll('files')).toEqual([a, b])
    expect(form.getAll('paths')).toEqual(['app/a.py', 'app/src/b.py'])
  })

  it('sends pasted code with its language', async () => {
    answer()
    await createTask('p-1', {
      title: '제목입니다',
      upload: { method: 'paste', code: 'print(1)', language: 'python' },
    })
    const form = sent()
    expect(form.get('upload_method')).toBe('paste')
    expect(form.get('code')).toBe('print(1)')
    expect(form.get('language')).toBe('python')
    expect(form.has('files')).toBe(false)
  })

  it('returns the CreateTaskResult', async () => {
    const result = makeCreateResult({ excluded_paths: ['.git/config'] })
    adapter.mockImplementation(async (c) => reply(c, 201, result))
    await expect(
      createTask('p-1', {
        title: '제목입니다',
        upload: { method: 'paste', code: 'x', language: 'c' },
      }),
    ).resolves.toEqual(result)
  })

  it('surfaces the server error with its suggestion', async () => {
    adapter.mockImplementation(async (c) =>
      reply(c, 415, {
        ...errorBody('unsupported_file_type', '지원하지 않는 파일 형식입니다 (.exe).'),
        suggestion: '지원되는 형식으로 변환하세요.',
      }),
    )
    const error = await createTask('p-1', {
      title: '제목입니다',
      upload: { method: 'file', files: [makeFile('a.exe')] },
    }).catch((e: unknown) => e)
    expect(isApiError(error) && error.suggestion).toBe('지원되는 형식으로 변환하세요.')
  })
})
