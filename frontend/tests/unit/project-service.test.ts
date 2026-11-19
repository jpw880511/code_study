import { describe, expect, it } from 'vitest'

import { isApiError } from '../../src/services/api-client'
import {
  createProject,
  deleteProject,
  getProject,
  listProjects,
  updateProject,
} from '../../src/services/project-service'
import { errorBody, mockApi, reply } from '../helpers/mock-api'
import { makeProject } from '../helpers/project-fixtures'

const adapter = mockApi()

function lastRequest() {
  const config = adapter.mock.calls[0][0]
  return {
    method: config.method,
    url: config.url,
    body: typeof config.data === 'string' ? JSON.parse(config.data) : config.data,
  }
}

describe('project-service', () => {
  it('listProjects: GET /projects and returns the array', async () => {
    const projects = [makeProject(), makeProject({ id: 'p-2' })]
    adapter.mockImplementation((c) => reply(c, 200, projects))
    await expect(listProjects()).resolves.toEqual(projects)
    expect(lastRequest()).toMatchObject({ method: 'get', url: '/projects' })
  })

  it('createProject: POST /projects with the given body and returns the project', async () => {
    const created = makeProject()
    adapter.mockImplementation((c) => reply(c, 201, created))
    await expect(createProject({ title: 'T', description: 'D' })).resolves.toEqual(created)
    expect(lastRequest()).toEqual({
      method: 'post',
      url: '/projects',
      body: { title: 'T', description: 'D' },
    })
  })

  it('createProject: sends no description key when none is given', async () => {
    adapter.mockImplementation((c) => reply(c, 201, makeProject()))
    await createProject({ title: 'T' })
    expect(lastRequest().body).toEqual({ title: 'T' })
  })

  it('getProject: GET /projects/{id}', async () => {
    adapter.mockImplementation((c) => reply(c, 200, makeProject({ id: 'abc' })))
    await expect(getProject('abc')).resolves.toMatchObject({ id: 'abc' })
    expect(lastRequest()).toMatchObject({ method: 'get', url: '/projects/abc' })
  })

  it('updateProject: PATCH sends only the given fields', async () => {
    adapter.mockImplementation((c) => reply(c, 200, makeProject({ title: 'New' })))
    await expect(updateProject('abc', { title: 'New' })).resolves.toMatchObject({ title: 'New' })
    expect(lastRequest()).toEqual({ method: 'patch', url: '/projects/abc', body: { title: 'New' } })
  })

  it('updateProject: an explicit null description is sent to clear it', async () => {
    adapter.mockImplementation((c) => reply(c, 200, makeProject({ description: null })))
    await updateProject('abc', { description: null })
    expect(lastRequest().body).toEqual({ description: null })
  })

  it('deleteProject: DELETE /projects/{id} resolves with nothing', async () => {
    adapter.mockImplementation((c) => reply(c, 204))
    await expect(deleteProject('abc')).resolves.toBeUndefined()
    expect(lastRequest()).toMatchObject({ method: 'delete', url: '/projects/abc' })
  })

  it('propagates server errors as ApiError with status and code', async () => {
    adapter.mockImplementation((c) =>
      reply(c, 404, errorBody('project_not_found', '프로젝트를 찾을 수 없습니다.')),
    )
    const error = await getProject('nope').catch((e: unknown) => e)
    expect(isApiError(error)).toBe(true)
    expect(error).toMatchObject({
      status: 404,
      code: 'project_not_found',
      message: '프로젝트를 찾을 수 없습니다.',
    })
  })
})
