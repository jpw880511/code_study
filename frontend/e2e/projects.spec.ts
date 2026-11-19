import { execFileSync } from 'node:child_process'
import { expect, test, type Page } from '@playwright/test'

// T057-T060: manual browser scenarios for projects, automated.
// A throwaway account is created in the dev database and removed afterwards.
const stamp = Date.now()
const email = `e2e-${stamp}@example.com`
const password = `E2e-${stamp}-Pw!`

function psql(sql: string): string {
  return execFileSync(
    'docker',
    ['exec', 'codelearning-db', 'psql', '-U', 'postgres', '-d', 'codelearning', '-At', '-c', sql],
    { encoding: 'utf8' },
  ).trim()
}

async function createProject(page: Page, title: string, description: string) {
  await page.getByRole('button', { name: '새 프로젝트' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('제목').fill(title)
  await dialog.getByLabel('설명').fill(description)
  await dialog.getByRole('button', { name: '만들기' }).click()
  await expect(dialog).toBeHidden()
}

test.describe.configure({ mode: 'serial' })

test.beforeAll(async ({ browser }) => {
  const page = await browser.newPage()
  await page.goto('/register')
  await page.getByLabel('이메일').fill(email)
  await page.getByLabel('비밀번호', { exact: true }).fill(password)
  await page.getByLabel('비밀번호 확인').fill(password)
  await page.getByRole('button', { name: '회원가입' }).click()
  await expect(page.getByRole('status')).toContainText('회원가입이 완료되었습니다')
  await page.close()
})

test.afterAll(() => {
  // projects (and the rest) go with the user: ON DELETE CASCADE
  psql(`delete from users where email = '${email}'`)
  expect(psql(`select count(*) from users where email = '${email}'`)).toBe('0')
})

test.beforeEach(async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('이메일').fill(email)
  await page.getByLabel('비밀번호').fill(password)
  await page.getByRole('button', { name: '로그인' }).click()
  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible()
})

test('T057 새 프로젝트를 만들면 대시보드에 나타난다', async ({ page }) => {
  await expect(page.getByText('아직 프로젝트가 없습니다')).toBeVisible()
  await createProject(page, 'E2E 프로젝트', '브라우저 테스트용 설명')
  const list = page.getByLabel('프로젝트 목록')
  await expect(list.getByText('E2E 프로젝트')).toBeVisible()
  await expect(list.getByTestId('project-card-description')).toHaveText('브라우저 테스트용 설명')
  await page.reload()
  await expect(page.getByLabel('프로젝트 목록').getByText('E2E 프로젝트')).toBeVisible()
})

test('T058 프로젝트 상세에 정보가 표시된다', async ({ page }) => {
  await page.getByLabel('프로젝트 목록').getByText('E2E 프로젝트').click()
  await expect(page).toHaveURL(/\/projects\/[0-9a-f-]{36}$/)
  await expect(page.getByRole('heading', { name: 'E2E 프로젝트' })).toBeVisible()
  await expect(page.getByText('브라우저 테스트용 설명')).toBeVisible()
  await expect(page.getByRole('button', { name: '수정' })).toBeVisible()
  await expect(page.getByRole('button', { name: '삭제' })).toBeVisible()
})

test('T059 제목을 수정하면 새로고침 후에도 유지된다', async ({ page }) => {
  await page.getByLabel('프로젝트 목록').getByText('E2E 프로젝트').click()
  await page.getByRole('button', { name: '수정' }).click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('제목').fill('E2E 프로젝트 (수정됨)')
  await dialog.getByRole('button', { name: '저장' }).click()
  await expect(page.getByRole('heading', { name: 'E2E 프로젝트 (수정됨)' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: 'E2E 프로젝트 (수정됨)' })).toBeVisible()
  expect(psql(`select title from projects p join users u on u.id = p.user_id where u.email = '${email}'`)).toBe(
    'E2E 프로젝트 (수정됨)',
  )
})

test('T060 삭제하면 목록에서 사라지고 DB에는 휴지통 상태로 남는다', async ({ page }) => {
  await page.getByLabel('프로젝트 목록').getByText('E2E 프로젝트 (수정됨)').click()
  await page.getByRole('button', { name: '삭제' }).click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('프로젝트 삭제')).toBeVisible()
  await dialog.getByRole('button', { name: '삭제', exact: true }).click()
  await expect(page).toHaveURL(/\/dashboard$|\/$/)
  await expect(page.getByText('E2E 프로젝트 (수정됨)')).toHaveCount(0)
  await expect(page.getByText('아직 프로젝트가 없습니다')).toBeVisible()

  const row = psql(
    `select deletion_status, trashed_at is not null, round(extract(epoch from (scheduled_deletion_at - trashed_at))/86400) ` +
      `from projects p join users u on u.id = p.user_id where u.email = '${email}'`,
  )
  expect(row).toBe('trashed|t|30')
})
