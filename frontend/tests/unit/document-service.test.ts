import { describe, expect, it } from 'vitest'

import { getDocument, getDocumentStatus } from '../../src/services/document-service'
import { errorBody, mockApi, networkFailure, reply, respondByRoute } from '../helpers/mock-api'
import { makeDocument, makeStatus } from '../helpers/document-fixtures'

const adapter = mockApi()

describe('getDocumentStatus', () => {
  it('returns the status body from GET /tasks/{id}/document/status', async () => {
    const status = makeStatus({
      status: 'in_progress',
      elapsed_seconds: 3,
      estimated_total_seconds: 20,
    })
    respondByRoute(adapter, { 'GET /tasks/t-1/document/status': (c) => reply(c, 200, status) })
    await expect(getDocumentStatus('t-1')).resolves.toEqual(status)
  })

  it('turns document_not_found into null instead of an error', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) =>
        reply(c, 404, errorBody('document_not_found', '이 Task에는 아직 학습 문서가 없습니다.')),
    })
    await expect(getDocumentStatus('t-1')).resolves.toBeNull()
  })

  it('keeps task_not_found and other failures as errors', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document/status': (c) =>
        reply(c, 404, errorBody('task_not_found', '요청한 Task를 찾을 수 없습니다.')),
    })
    await expect(getDocumentStatus('t-1')).rejects.toMatchObject({ code: 'task_not_found' })
    adapter.mockImplementation(async (c) => networkFailure(c))
    await expect(getDocumentStatus('t-1')).rejects.toMatchObject({ code: 'network_error' })
  })
})

describe('getDocument', () => {
  it('returns the document from GET /tasks/{id}/document', async () => {
    const doc = makeDocument()
    respondByRoute(adapter, { 'GET /tasks/t-1/document': (c) => reply(c, 200, doc) })
    await expect(getDocument('t-1')).resolves.toEqual(doc)
  })

  it('turns document_not_found into null and keeps other errors', async () => {
    respondByRoute(adapter, {
      'GET /tasks/t-1/document': (c) => reply(c, 404, errorBody('document_not_found')),
      'GET /tasks/t-2/document': (c) => reply(c, 403, errorBody('task_forbidden')),
    })
    await expect(getDocument('t-1')).resolves.toBeNull()
    await expect(getDocument('t-2')).rejects.toMatchObject({ code: 'task_forbidden' })
  })
})
