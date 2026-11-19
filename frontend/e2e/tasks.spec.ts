import { execFileSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, test, type Locator, type Page } from '@playwright/test'

// T084-T089: browser tests for creating tasks and uploading code, automated.
// Needs the dev servers (frontend 5173, backend 8000) and the Docker database.
// A throwaway account is created in the dev database and removed afterwards.
const stamp = Date.now()
const email = `e2e-tasks-${stamp}@example.com`
const password = `E2e-${stamp}-Pw!`
const API = 'http://localhost:8000/api/v1'
const MB = 1024 * 1024

function psql(sql: string): string {
  return execFileSync(
    'docker',
    ['exec', 'codelearning-db', 'psql', '-U', 'postgres', '-d', 'codelearning', '-At', '-c', sql],
    { encoding: 'utf8' },
  ).trim()
}

// How many tasks (trashed ones included) the test account has in the project of that title.
function taskCount(projectTitle: string): number {
  return Number(
    psql(
      `select count(*) from tasks t join projects p on p.id = t.project_id join users u on u.id = p.user_id ` +
        `where u.email = '${email}' and p.title = '${projectTitle}'`,
    ),
  )
}

async function createProject(page: Page, title: string) {
  await page.goto('/')
  await page.getByRole('button', { name: '새 프로젝트' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('제목').fill(title)
  await dialog.getByRole('button', { name: '만들기' }).click()
  await expect(dialog).toBeHidden()
  await page.getByLabel('프로젝트 목록').getByText(title).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
}

async function openModal(page: Page, taskTitle: string): Promise<Locator> {
  await page.getByRole('button', { name: '새 Task' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('제목').fill(taskTitle)
  return dialog
}

async function confirmUpload(page: Page) {
  await page
    .getByRole('dialog', { name: '업로드 확인' })
    .getByRole('button', { name: '확인' })
    .click()
}

const taskList = (page: Page) => page.getByLabel('Task 목록')

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
  // projects, tasks and code rows go with the user: ON DELETE CASCADE
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

test('T084 파일 하나를 올리면 Task 1이 만들어진다', async ({ page }) => {
  await createProject(page, 'T084 프로젝트')
  const dialog = await openModal(page, '계산기 함수 학습')
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'main.py',
    mimeType: 'text/x-python',
    buffer: Buffer.from('def add(a, b):\n    return a + b\n\nprint(add(1, 2))\n'),
  })
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()

  const confirm = page.getByRole('dialog', { name: '업로드 확인' })
  await expect(confirm.getByText('Task 1')).toBeVisible()
  await expect(confirm.getByLabel('업로드된 파일').getByText('main.py')).toBeVisible()
  await confirmUpload(page)

  const card = taskList(page).getByRole('link').first()
  await expect(card).toContainText('Task 1')
  await expect(card).toContainText('계산기 함수 학습')
  await expect(card).toContainText('python · 초급 · 파일 1개 · 3줄')
  expect(
    psql(
      `select t.task_number || ':' || t.upload_method from tasks t join projects p on p.id = t.project_id where p.title = 'T084 프로젝트'`,
    ),
  ).toBe('1:file')
})

test('T085 폴더를 올리면 폴더 구조가 보존된다', async ({ page }) => {
  const root = mkdtempSync(join(tmpdir(), 'folder-e2e-'))
  const app = join(root, 'my app')
  for (const dir of ['src', 'public', 'node_modules/lib', '.git']) {
    mkdirSync(join(app, dir), { recursive: true })
  }
  writeFileSync(join(app, 'src/App.jsx'), 'export default function App() { return <div /> }\n')
  writeFileSync(join(app, 'src/한글 파일.js'), 'const x = (a) => a + 1;\n')
  writeFileSync(join(app, 'public/index.html'), '<html><body></body></html>\n')
  writeFileSync(join(app, 'node_modules/lib/index.js'), 'module.exports = 1;\n')
  writeFileSync(join(app, '.git/config'), '[core]\n')

  await createProject(page, 'T085 프로젝트')
  const dialog = await openModal(page, '폴더 업로드 작업')
  await dialog.getByRole('tab', { name: '폴더 업로드' }).click()
  await dialog.locator('input[type="file"]').setInputFiles(app)
  await expect(dialog.getByRole('status')).toContainText('일반적인 빌드/시스템 폴더를 제외했습니다')
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()

  const list = page.getByRole('dialog', { name: '업로드 확인' }).getByLabel('업로드된 파일')
  await expect(list.getByText('my app/src/App.jsx')).toBeVisible()
  await expect(list.getByText('my app/src/한글 파일.js')).toBeVisible()
  await expect(list.getByText('my app/public/index.html')).toBeVisible()
  await expect(list.getByText('node_modules')).toHaveCount(0)
  await confirmUpload(page)

  // The structure is stored, not only shown: it comes back on the task page after a reload.
  await taskList(page).getByText('폴더 업로드 작업').click()
  await page.reload()
  const files = page.getByLabel('업로드된 파일')
  await expect(files.getByText('my app/src/App.jsx')).toBeVisible()
  await expect(files.getByText('my app/public/index.html')).toBeVisible()
  expect(
    psql(
      `select string_agg(c.file_path, '|' order by c.file_path) from code_files c join uploaded_code uc on uc.id = c.uploaded_code_id ` +
        `join tasks t on t.id = uc.task_id join projects p on p.id = t.project_id where p.title = 'T085 프로젝트'`,
    ),
  ).toBe('my app/public/index.html|my app/src/App.jsx|my app/src/한글 파일.js')
})

test('T086 코드를 붙여넣으면 고른 언어로 저장된다', async ({ page }) => {
  await createProject(page, 'T086 프로젝트')
  const dialog = await openModal(page, '붙여넣은 코드 작업')
  await dialog.getByRole('tab', { name: '코드 붙여넣기' }).click()
  await dialog.getByLabel('프로그래밍 언어').selectOption('python')
  await dialog.getByLabel('코드', { exact: true }).fill("def hello():\n    print('hello')\n")
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()

  const confirm = page.getByRole('dialog', { name: '업로드 확인' })
  await expect(confirm.getByLabel('업로드된 파일').getByText('pasted_code.py')).toBeVisible()
  await confirmUpload(page)
  await expect(taskList(page).getByRole('link').first()).toContainText('python · 초급')
  expect(
    psql(
      `select uc.detected_language || ':' || t.upload_method from uploaded_code uc join tasks t on t.id = uc.task_id ` +
        `join projects p on p.id = t.project_id where p.title = 'T086 프로젝트'`,
    ),
  ).toBe('python:paste')
})

test('T087 11MB 파일은 오류 메시지와 함께 거부된다', async ({ page }) => {
  await createProject(page, 'T087 프로젝트')
  const dialog = await openModal(page, '큰 파일 업로드')
  const big = { name: 'big.py', mimeType: 'text/x-python', buffer: Buffer.alloc(11 * MB, 97) }
  await dialog.locator('input[type="file"]').setInputFiles(big)

  // The browser says so right away, before anything is sent.
  await expect(dialog.getByRole('alert')).toContainText('파일 크기가 10MB를 초과합니다.')
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()
  await expect(dialog).toBeVisible()
  expect(taskCount('T087 프로젝트')).toBe(0)

  // The server refuses it as well, for a client that skips the browser check.
  const projectId = psql(`select id from projects where title = 'T087 프로젝트' limit 1`)
  const response = await page.request.post(`${API}/projects/${projectId}/tasks`, {
    multipart: {
      title: '서버에 직접 보낸 큰 파일',
      upload_method: 'file',
      files: big,
    },
  })
  expect(response.status()).toBe(413)
  const body = await response.json()
  expect(body.error).toBe('file_too_large')
  expect(body.message).toBe('파일 크기가 10MB를 초과합니다.')
  expect(body.details.max_size_mb).toBe(10)
  expect(taskCount('T087 프로젝트')).toBe(0)
})

test('T088 바이너리 파일은 오류 메시지와 함께 거부된다', async ({ page }) => {
  await createProject(page, 'T088 프로젝트')
  const dialog = await openModal(page, '바이너리 업로드')
  // A PNG renamed to .py: the browser cannot tell, so the server must.
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    Buffer.alloc(64),
  ])
  await dialog
    .locator('input[type="file"]')
    .setInputFiles({ name: 'fake.py', mimeType: 'text/x-python', buffer: png })
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()

  const alert = dialog.getByRole('alert')
  await expect(alert).toContainText('바이너리 파일은 업로드할 수 없습니다.')
  await expect(alert).toContainText('소스 코드 텍스트 파일만 지원합니다')
  await expect(dialog).toBeVisible()
  expect(taskCount('T088 프로젝트')).toBe(0)
})

test('T089 Task를 연달아 3개 만들면 번호가 1, 2, 3이다', async ({ page }) => {
  await createProject(page, 'T089 프로젝트')
  for (const n of [1, 2, 3]) {
    const dialog = await openModal(page, `연속 작업 ${n}번째`)
    await dialog.getByRole('tab', { name: '코드 붙여넣기' }).click()
    await dialog.getByLabel('프로그래밍 언어').selectOption('python')
    await dialog.getByLabel('코드', { exact: true }).fill(`print(${n})\n`)
    await dialog.getByRole('button', { name: 'Task 만들기' }).click()
    await expect(
      page.getByRole('dialog', { name: '업로드 확인' }).getByText(`Task ${n}`, { exact: true }),
    ).toBeVisible()
    await confirmUpload(page)
    await expect(taskList(page).getByRole('link')).toHaveCount(n)
  }

  const expected = ['Task 1', 'Task 2', 'Task 3']
  await expect(taskList(page).getByText(/^Task \d+$/)).toHaveText(expected)
  await page.reload()
  await expect(taskList(page).getByText(/^Task \d+$/)).toHaveText(expected)
  expect(
    psql(
      `select string_agg(t.task_number::text, ',' order by t.task_number) from tasks t join projects p on p.id = t.project_id where p.title = 'T089 프로젝트'`,
    ),
  ).toBe('1,2,3')
})
