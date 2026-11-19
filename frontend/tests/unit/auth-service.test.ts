import { describe, expect, it } from 'vitest'

import { isApiError } from '../../src/services/api-client'
import * as authService from '../../src/services/auth-service'
import { errorBody, reply, mockApi } from '../helpers/mock-api'

const user = { id: 'u-1', email: 'a@example.com', skill_level: null }
const adapter = mockApi()

function lastRequest() {
  const config = adapter.mock.calls.at(-1)![0]
  return { method: config.method, url: config.url, body: config.data && JSON.parse(config.data) }
}

describe('auth-service', () => {
  it('register posts the credentials to /auth/register and returns the user', async () => {
    adapter.mockImplementation((config) => reply(config, 201, user))
    await expect(authService.register('a@example.com', 'abcd1234')).resolves.toEqual(user)
    expect(lastRequest()).toEqual({
      method: 'post',
      url: '/auth/register',
      body: { email: 'a@example.com', password: 'abcd1234' },
    })
  })

  it('login posts the credentials to /auth/login and returns the user', async () => {
    adapter.mockImplementation((config) => reply(config, 200, user))
    await expect(authService.login('a@example.com', 'abcd1234')).resolves.toEqual(user)
    expect(lastRequest()).toEqual({
      method: 'post',
      url: '/auth/login',
      body: { email: 'a@example.com', password: 'abcd1234' },
    })
  })

  it('me gets /auth/me and returns the user', async () => {
    adapter.mockImplementation((config) => reply(config, 200, user))
    await expect(authService.me()).resolves.toEqual(user)
    expect(lastRequest()).toMatchObject({ method: 'get', url: '/auth/me' })
  })

  it('logout posts to /auth/logout and returns nothing', async () => {
    adapter.mockImplementation((config) => reply(config, 204))
    await expect(authService.logout()).resolves.toBeUndefined()
    expect(lastRequest()).toMatchObject({ method: 'post', url: '/auth/logout' })
  })

  it('refresh posts to /auth/refresh and returns nothing', async () => {
    adapter.mockImplementation((config) => reply(config, 204))
    await expect(authService.refresh()).resolves.toBeUndefined()
    expect(lastRequest()).toMatchObject({ method: 'post', url: '/auth/refresh' })
  })

  it.each([
    ['register', () => authService.register('a@example.com', 'x'), 409, 'email_already_registered'],
    ['login', () => authService.login('a@example.com', 'x'), 401, 'invalid_credentials'],
    ['me', () => authService.me(), 401, 'not_authenticated'],
    ['refresh', () => authService.refresh(), 401, 'session_expired'],
  ])('%s propagates the ApiError', async (_name, call, status, code) => {
    adapter.mockImplementation((config) => reply(config, status, errorBody(code, '서버 메시지')))
    const error = await call().catch((e: unknown) => e)
    expect(isApiError(error)).toBe(true)
    expect(error).toMatchObject({ status, code, message: '서버 메시지' })
  })
})
