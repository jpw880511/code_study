import { execFileSync, spawn, spawnSync, type ChildProcess } from 'node:child_process'
import { mkdirSync, mkdtempSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { expect, test, type APIRequestContext, type Page } from '@playwright/test'
import { BACKEND_DIR, PYTHON, UPLOAD_DIR } from './full-flow.env'

// The whole product flow, from sign-up to a generated learning document, in one serial run.
// Run it with `npm run test:e2e:full` (see playwright.full-flow.config.ts). Only scenario 5 calls
// the real Gemini API; the other documents are written by hand into the database.
const stamp = Date.now()
const API = 'http://localhost:8000/api/v1'
const MB = 1024 * 1024
const USER_A = { email: `ff-a-${stamp}@example.com`, password: `Ff-${stamp}-Pw!` }
const USER_B = { email: `ff-b-${stamp}@example.com`, password: `Ff-${stamp}-Pw!` }

function psql(sql: string): string {
  return execFileSync(
    'docker',
    [
      'exec',
      '-i',
      'codelearning-db',
      'psql',
      '-U',
      'postgres',
      '-d',
      'codelearning',
      '-At',
      '-v',
      'ON_ERROR_STOP=1',
      '-f',
      '-',
    ],
    { encoding: 'utf8', input: sql },
  ).trim()
}

const docker = (...args: string[]) => spawnSync('docker', args, { encoding: 'utf8' })

const SMALL_CODE = 'def add(a, b):\n    return a + b\n\nprint(add(3, 4))\n'

// About 87 lines, so that Monaco has something to scroll through.
function longCode(): string {
  const out = ['# 점수 계산 프로그램', 'scores = {"민지": 90, "철수": 72}', '']
  for (let i = 1; i <= 7; i++) {
    out.push(
      `def grade_${i}(score):`,
      `    """${i}번 규칙."""`,
      `    if score >= ${100 - i * 5}:`,
      '        return "A"',
      '    return "B"',
      '',
    )
  }
  for (let i = 0; i < 40; i++) out.push(`total_${i} = sum(scores.values()) + ${i}`)
  out.push('print("끝")')
  return out.join('\n') + '\n'
}
const LONG_CODE = longCode()
const LONG_LINES = LONG_CODE.split('\n').length - 1
const ENTRIES = [
  { s: 1, e: 2 },
  { s: 4, e: 9 },
  { s: 22, e: 27 },
  { s: 46, e: 52 },
  { s: LONG_LINES, e: LONG_LINES },
]
const label = (s: number, e: number) => (s === e ? `${s}줄` : `${s}~${e}줄`)
const FILE = 'pasted_code.py'

// A document written by hand with the structure of the real one (no AI call).
function handMadeDocument() {
  return {
    chapter1: { title: '이 코드가 하는 일', summary: '점수에 등급을 매깁니다.' },
    chapter2: {
      title: '미리 알아야 할 지식',
      concepts: Array.from({ length: 5 }, (_, n) => ({
        name: `개념${n + 1}`,
        explanation: '쉬운 설명입니다.',
        analogy: '상자와 같습니다.',
        example: 'x = 1',
        use_cases: '어디서나 쓰입니다.\n두 번째 줄입니다.',
      })),
    },
    chapter3: {
      title: '코드 구조 한눈에 보기',
      flowchart: '시작 -> 등급 -> 끝',
      file_breakdown: { [FILE]: '등급을 매깁니다.' },
    },
    chapter4: {
      title: '한 줄씩 설명',
      explanations: ENTRIES.map(({ s, e }, n) => ({
        file: FILE,
        line_start: s,
        line_end: e,
        code: `코드 조각 ${n + 1}`,
        what_it_does: `${n + 1}번째 설명입니다.`,
        syntax_breakdown: '',
        analogy: '',
        alternatives: '',
        notes: '',
      })),
    },
    chapter5: {
      title: '실행 흐름 따라가기',
      steps: [
        { step: 1, description: '시작', data: '' },
        { step: 2, description: '끝', data: '' },
      ],
    },
    chapter6: {
      title: '핵심 개념 정리',
      concepts: [
        {
          name: '변수',
          what_it_is: '상자',
          why_its_used: '담으려고',
          where_its_applied: '어디서나',
        },
      ],
    },
    chapter7: {
      title: '흔한 실수',
      mistakes: Array.from({ length: 3 }, () => ({
        wrong: 'x =',
        right: 'x = 1',
        why: '값이 없어서',
        fix: '값을 씁니다',
      })),
    },
  }
}

// ---------------------------------------------------------------- helpers

async function register(page: Page, user: { email: string; password: string }) {
  await page.goto('/register')
  await page.getByLabel('이메일').fill(user.email)
  await page.getByLabel('비밀번호', { exact: true }).fill(user.password)
  await page.getByLabel('비밀번호 확인').fill(user.password)
  await page.getByRole('button', { name: '회원가입' }).click()
}

async function login(page: Page, user: { email: string; password: string }) {
  await page.goto('/login')
  await page.getByLabel('이메일').fill(user.email)
  await page.getByLabel('비밀번호').fill(user.password)
  await page.getByRole('button', { name: '로그인' }).click()
  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible()
}

async function createProject(page: Page, title: string, description = '') {
  await page.getByRole('button', { name: '새 프로젝트' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('제목').fill(title)
  if (description) await dialog.getByLabel('설명').fill(description)
  await dialog.getByRole('button', { name: '만들기' }).click()
  await expect(dialog).toBeHidden()
}

async function openProject(page: Page, title: string) {
  await page.goto('/')
  await page.getByLabel('프로젝트 목록').getByText(title).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
}

async function projectId(request: APIRequestContext, title: string): Promise<string> {
  const projects: { id: string; title: string }[] = await (
    await request.get(`${API}/projects`)
  ).json()
  const found = projects.find((p) => p.title === title)
  expect(found, `project "${title}"`).toBeTruthy()
  return found!.id
}

async function apiUpload(
  request: APIRequestContext,
  project: string,
  title: string,
  code: string,
): Promise<string> {
  const response = await request.post(`${API}/projects/${project}/tasks`, {
    multipart: { title, upload_method: 'paste', code, language: 'python' },
  })
  expect(response.status()).toBe(201)
  return (await response.json()).id
}

async function openTaskModal(page: Page, title: string) {
  await page.getByRole('button', { name: '새 Task' }).first().click()
  const dialog = page.getByRole('dialog')
  await dialog.getByLabel('제목').fill(title)
  return dialog
}

async function pasteTask(page: Page, title: string, code: string) {
  const dialog = await openTaskModal(page, title)
  await dialog.getByRole('tab', { name: '코드 붙여넣기' }).click()
  await dialog.getByLabel('프로그래밍 언어').selectOption('python')
  await dialog.getByLabel('코드', { exact: true }).fill(code)
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()
}

const confirmUpload = (page: Page) =>
  page.getByRole('dialog', { name: '업로드 확인' }).getByRole('button', { name: '확인' }).click()
const taskList = (page: Page) => page.getByLabel('Task 목록')
const taskCount = () =>
  Number(
    psql(
      `select count(*) from tasks t join projects p on p.id = t.project_id join users u on u.id = p.user_id where u.email = '${USER_A.email}';`,
    ),
  )

const editorOf = (page: Page) => page.locator('.monaco-editor').first()
const visibleNumbers = (page: Page) =>
  editorOf(page)
    .locator('.line-numbers')
    .evaluateAll((nodes) => {
      const box = (nodes[0]?.closest('.monaco-editor') as HTMLElement).getBoundingClientRect()
      return nodes
        .filter((n) => {
          const r = n.getBoundingClientRect()
          return r.top >= box.top && r.bottom <= box.bottom
        })
        .map((n) => Number(n.textContent))
        .filter((n) => n > 0)
    })

// The Celery worker, started only for the scenario that really calls Gemini.
let worker: ChildProcess | null = null
async function startWorker() {
  const child = spawn(
    PYTHON,
    [
      '-X',
      'utf8',
      '-m',
      'celery',
      '-A',
      'src.tasks.celery_app',
      'worker',
      '-Q',
      'document_generation',
      '--pool=solo',
      '-l',
      'info',
      '-n',
      `fullflow-${stamp}@%h`,
    ],
    {
      cwd: BACKEND_DIR,
      env: { ...process.env, UPLOAD_STORAGE_PATH: UPLOAD_DIR, PYTHONIOENCODING: 'utf-8' },
    },
  )
  worker = child
  await new Promise<void>((resolve, reject) => {
    const timer = setTimeout(
      () => reject(new Error('the Celery worker did not become ready in 60 s')),
      60_000,
    )
    const onData = (chunk: Buffer) => {
      if (chunk.toString('utf8').includes(' ready.')) {
        clearTimeout(timer)
        resolve()
      }
    }
    child.stdout?.on('data', onData)
    child.stderr?.on('data', onData)
    child.on('exit', () => reject(new Error('the Celery worker exited early')))
  })
}
function stopWorker() {
  if (worker?.pid) spawnSync('taskkill', ['/F', '/T', '/PID', String(worker.pid)])
  worker = null
}

test.describe.configure({ mode: 'serial' })

// State shared by the scenarios.
let projectMain = ''
let taskIds = { file: '', folder: '', paste: '' }
let aiTaskUrl = ''
let seededTaskUrl = ''
let trashedTaskId = ''
let trashedProjectTitle = ''

test.beforeAll(() => {
  const ping = docker('exec', 'codelearning-redis', 'redis-cli', 'ping')
  expect(ping.stdout.trim(), 'Redis must be running (docker compose up -d)').toBe('PONG')
  expect(psql('select 1;')).toBe('1')
})

test.afterAll(() => {
  stopWorker()
  docker('start', 'codelearning-redis') // a scenario may have stopped it
  psql(`delete from users where email in ('${USER_A.email}', '${USER_B.email}');`)
  expect(psql(`select count(*) from users where email like 'ff-%-${stamp}@example.com';`)).toBe('0')
  docker('exec', 'codelearning-redis', 'redis-cli', 'del', 'document_generation')
})

// ======================================================= 1. authentication

test('1. 인증: 가입 검증, 중복, 로그인 실패/성공, 세션 유지, 로그아웃, 보호 라우트', async ({
  page,
}) => {
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/) // not logged in: sent to the login page

  await page.goto('/register')
  await page.getByRole('button', { name: '회원가입' }).click()
  await expect(page.getByText('이메일을 입력하세요.')).toBeVisible()
  await expect(page.getByText('비밀번호를 입력하세요.').first()).toBeVisible()

  const email = page.getByLabel('이메일')
  const password = page.getByLabel('비밀번호', { exact: true })
  const submit = page.getByRole('button', { name: '회원가입' })
  await email.fill('abc')
  await submit.click()
  await expect(page.getByText('올바른 이메일 형식이 아닙니다.')).toBeVisible()
  await email.fill(USER_A.email)
  for (const [value, message] of [
    ['short1', '비밀번호는 8자 이상이어야 합니다.'],
    ['longenough', '비밀번호에 숫자를 포함하세요.'],
    ['12345678', '비밀번호에 영문자를 포함하세요.'],
  ] as const) {
    await password.fill(value)
    await submit.click()
    await expect(page.getByText(message)).toBeVisible()
  }
  await password.fill(USER_A.password)
  await page.getByLabel('비밀번호 확인').fill('different1')
  await submit.click()
  await expect(page.getByText('비밀번호가 일치하지 않습니다.')).toBeVisible()
  expect(psql(`select count(*) from users where email = '${USER_A.email}';`)).toBe('0') // nothing was created

  await register(page, USER_A)
  await expect(page.getByRole('status')).toContainText('회원가입이 완료되었습니다')
  await expect(page).toHaveURL(/\/login$/)

  await register(page, USER_A) // the same e-mail again
  await expect(page.getByRole('alert')).toContainText('이미 가입된 이메일입니다.')

  await page.goto('/login')
  await page.getByLabel('이메일').fill(USER_A.email)
  await page.getByLabel('비밀번호').fill('Wrong-password-1')
  await page.getByRole('button', { name: '로그인' }).click()
  await expect(page.getByRole('alert')).toContainText('이메일 또는 비밀번호가 올바르지 않습니다.')
  await expect(page).toHaveURL(/\/login$/)

  await login(page, USER_A)
  await page.reload()
  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible() // the session survives a reload

  await page.getByRole('button', { name: '로그아웃' }).click()
  await expect(page).toHaveURL(/\/login$/)
  await page.goto('/')
  await expect(page).toHaveURL(/\/login$/) // and the app is closed again

  // Account B for the isolation scenario.
  const registered = await page.request.post(`${API}/auth/register`, { data: USER_B })
  expect(registered.status()).toBe(201)
})

// ============================================================= 2. projects

test('2. 프로젝트: 생성 검증, 목록, 상세, 수정, 삭제', async ({ page }) => {
  await login(page, USER_A)
  await expect(
    page.getByText('아직 프로젝트가 없습니다. 첫 프로젝트를 만들어 보세요.'),
  ).toBeVisible()

  await page.getByRole('button', { name: '새 프로젝트' }).first().click()
  const dialog = page.getByRole('dialog')
  await expect(dialog.getByText('2000자 남음')).toBeVisible()
  await dialog.getByLabel('설명').fill('가나다라마')
  await expect(dialog.getByText('1995자 남음')).toBeVisible()
  await dialog.getByRole('button', { name: '만들기' }).click()
  await expect(dialog.getByText('프로젝트 제목은 최소 1자 이상이어야 합니다.')).toBeVisible()
  await dialog.getByLabel('제목').fill('가'.repeat(256))
  await dialog.getByRole('button', { name: '만들기' }).click()
  await expect(dialog.getByText('프로젝트 제목은 최대 255자까지 입력 가능합니다.')).toBeVisible()
  await dialog.getByRole('button', { name: '취소' }).click()
  await expect(dialog).toBeHidden()
  expect(
    psql(
      `select count(*) from projects p join users u on u.id = p.user_id where u.email = '${USER_A.email}';`,
    ),
  ).toBe('0')

  await createProject(page, '메인 프로젝트', '전체 흐름 테스트용 설명')
  await createProject(page, '삭제할 프로젝트')
  const list = page.getByLabel('프로젝트 목록')
  await expect(list.getByText('메인 프로젝트')).toBeVisible()
  await expect(list.getByText('삭제할 프로젝트')).toBeVisible()

  await openProject(page, '메인 프로젝트')
  await expect(page.getByText('전체 흐름 테스트용 설명')).toBeVisible()
  projectMain = await projectId(page.request, '메인 프로젝트')

  await page.getByRole('button', { name: '수정' }).click()
  await page.getByRole('dialog').getByLabel('제목').fill('메인 프로젝트 (수정됨)')
  await page.getByRole('dialog').getByRole('button', { name: '저장' }).click()
  await expect(page.getByRole('heading', { name: '메인 프로젝트 (수정됨)' })).toBeVisible()
  await page.reload()
  await expect(page.getByRole('heading', { name: '메인 프로젝트 (수정됨)' })).toBeVisible()
  await page.getByRole('button', { name: '수정' }).click()
  await page.getByRole('dialog').getByLabel('제목').fill('메인 프로젝트')
  await page.getByRole('dialog').getByRole('button', { name: '저장' }).click()
  await expect(page.getByRole('heading', { name: '메인 프로젝트', exact: true })).toBeVisible()

  // Delete: cancel keeps it, confirm trashes it together with its tasks.
  trashedProjectTitle = '삭제할 프로젝트'
  const trashedProject = await projectId(page.request, trashedProjectTitle)
  trashedTaskId = await apiUpload(page.request, trashedProject, '삭제될 Task 입니다', SMALL_CODE)
  await openProject(page, trashedProjectTitle)
  await page.getByRole('button', { name: '삭제' }).click()
  const confirm = page.getByRole('dialog', { name: '프로젝트 삭제' })
  await expect(confirm).toContainText('이 프로젝트를 삭제할까요?')
  await confirm.getByRole('button', { name: '취소' }).click()
  await expect(confirm).toBeHidden()
  await expect(page.getByRole('heading', { name: trashedProjectTitle })).toBeVisible()
  await page.getByRole('button', { name: '삭제' }).click()
  await page
    .getByRole('dialog', { name: '프로젝트 삭제' })
    .getByRole('button', { name: '삭제', exact: true })
    .click()
  await expect(page.getByRole('heading', { name: '대시보드' })).toBeVisible()
  await expect(page.getByLabel('프로젝트 목록').getByText(trashedProjectTitle)).toHaveCount(0)
  expect(psql(`select deletion_status from projects where title = '${trashedProjectTitle}';`)).toBe(
    'trashed',
  )
  expect(psql(`select deletion_status from tasks where id = '${trashedTaskId}';`)).toBe('trashed') // its task went along
  await page.goto(`/tasks/${trashedTaskId}`)
  await expect(page.getByRole('alert')).toContainText('요청한 Task를 찾을 수 없습니다.')
})

// ================================================= 3. uploads that are fine

test('3. Task 업로드(정상): 파일, 폴더, 붙여넣기, 번호 1·2·3', async ({ page }) => {
  await login(page, USER_A)
  await openProject(page, '메인 프로젝트')

  // 3.1 one file -> Task 1
  let dialog = await openTaskModal(page, '파일로 올린 Task')
  await dialog.locator('input[type="file"]').setInputFiles({
    name: 'main.py',
    mimeType: 'text/x-python',
    buffer: Buffer.from(SMALL_CODE),
  })
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()
  let confirm = page.getByRole('dialog', { name: '업로드 확인' })
  await expect(confirm.getByText('Task 1', { exact: true })).toBeVisible()
  await expect(confirm.getByLabel('업로드된 파일').getByText('main.py')).toBeVisible()
  await confirmUpload(page)

  // 3.2 a folder -> Task 2, structure kept, system folders left out
  const root = mkdtempSync(join(tmpdir(), 'fullflow-folder-'))
  const app = join(root, 'my app')
  for (const dir of ['src', 'public', 'node_modules/lib', '.git'])
    mkdirSync(join(app, dir), { recursive: true })
  writeFileSync(join(app, 'src/App.jsx'), 'export default function App() { return <div /> }\n')
  writeFileSync(join(app, 'src/한글 파일.js'), 'const x = (a) => a + 1;\n')
  writeFileSync(join(app, 'public/index.html'), '<html><body></body></html>\n')
  writeFileSync(join(app, 'node_modules/lib/index.js'), 'module.exports = 1;\n')
  writeFileSync(join(app, '.git/config'), '[core]\n')
  dialog = await openTaskModal(page, '폴더로 올린 Task')
  await dialog.getByRole('tab', { name: '폴더 업로드' }).click()
  await dialog.locator('input[type="file"]').setInputFiles(app)
  await expect(dialog.getByRole('status')).toContainText('일반적인 빌드/시스템 폴더를 제외했습니다')
  await dialog.getByRole('button', { name: 'Task 만들기' }).click()
  confirm = page.getByRole('dialog', { name: '업로드 확인' })
  const files = confirm.getByLabel('업로드된 파일')
  await expect(files.getByText('my app/src/App.jsx')).toBeVisible()
  await expect(files.getByText('my app/src/한글 파일.js')).toBeVisible()
  await expect(files.getByText('my app/public/index.html')).toBeVisible()
  await expect(files.getByText('node_modules')).toHaveCount(0)
  await confirmUpload(page)

  // 3.3 pasted code -> Task 3
  await pasteTask(page, '붙여넣은 Task', SMALL_CODE)
  await expect(
    page
      .getByRole('dialog', { name: '업로드 확인' })
      .getByLabel('업로드된 파일')
      .getByText('pasted_code.py'),
  ).toBeVisible()
  await confirmUpload(page)

  await expect(taskList(page).getByText(/^Task \d+$/)).toHaveText(['Task 1', 'Task 2', 'Task 3'])
  await expect(taskList(page).getByRole('link').first()).toContainText(
    'python · 초급 · 파일 1개 · 3줄',
  )
  await expect(taskList(page).getByRole('link').nth(1)).toContainText('javascript')
  await page.reload()
  await expect(taskList(page).getByText(/^Task \d+$/)).toHaveText(['Task 1', 'Task 2', 'Task 3'])
  const rows = psql(
    `select t.id || '|' || t.upload_method from tasks t where t.project_id = '${projectMain}' order by t.task_number;`,
  ).split('\n')
  taskIds = {
    file: rows[0].split('|')[0],
    folder: rows[1].split('|')[0],
    paste: rows[2].split('|')[0],
  }
  expect(rows.map((r) => r.split('|')[1])).toEqual(['file', 'folder', 'paste'])
  expect(
    psql(
      `select string_agg(c.file_path, ',' order by c.file_path) from code_files c join uploaded_code uc on uc.id = c.uploaded_code_id where uc.task_id = '${taskIds.folder}';`,
    ),
  ).toBe('my app/public/index.html,my app/src/App.jsx,my app/src/한글 파일.js')
})

// ================================================ 4. uploads that are refused

test('4. Task 업로드(거부): 형식, 용량, 바이너리, 개수, 언어, 제목', async ({ page }) => {
  await login(page, USER_A)
  await openProject(page, '메인 프로젝트')
  const before = taskCount()
  const dialog = await openTaskModal(page, '거부 확인 작업')
  const input = dialog.locator('input[type="file"]')
  const submit = dialog.getByRole('button', { name: 'Task 만들기' })
  const alert = dialog.getByRole('alert')

  await input.setInputFiles({
    name: 'virus.exe',
    mimeType: 'application/octet-stream',
    buffer: Buffer.from('x'),
  })
  await submit.click()
  await expect(alert).toContainText('지원하지 않는 파일 형식입니다')
  await dialog.getByRole('button', { name: 'virus.exe 제거' }).click()

  await input.setInputFiles({
    name: 'big.py',
    mimeType: 'text/x-python',
    buffer: Buffer.alloc(11 * MB, 97),
  })
  await expect(alert).toContainText('파일 크기가 10MB를 초과합니다.')
  await dialog.getByRole('button', { name: 'big.py 제거' }).click()

  const many = Array.from({ length: 21 }, (_, i) => ({
    name: `f${i}.py`,
    mimeType: 'text/x-python',
    buffer: Buffer.from('x = 1\n'),
  }))
  await input.setInputFiles(many)
  await expect(alert).toContainText('업로드당 최대 20개 파일까지 가능합니다.')
  for (let i = 0; i < 21; i++) await dialog.getByRole('button', { name: `f${i}.py 제거` }).click()

  // A PNG renamed to .py: only the server can tell.
  const png = Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    Buffer.alloc(64),
  ])
  await input.setInputFiles({ name: 'fake.py', mimeType: 'text/x-python', buffer: png })
  await submit.click()
  await expect(alert).toContainText('바이너리 파일은 업로드할 수 없습니다.')
  await expect(alert).toContainText('소스 코드 텍스트 파일만 지원합니다')
  await expect(dialog).toBeVisible()

  await dialog.getByRole('tab', { name: '코드 붙여넣기' }).click()
  await dialog.getByLabel('코드', { exact: true }).fill('x = 1\n')
  await submit.click()
  await expect(dialog.getByText('업로드하기 전에 프로그래밍 언어를 선택하세요.')).toBeVisible()

  await dialog.getByLabel('제목').fill('짧음')
  await dialog.getByLabel('프로그래밍 언어').selectOption('python')
  await submit.click()
  await expect(dialog.getByText('Task 제목은 최소 5자 이상이어야 합니다.')).toBeVisible()

  await dialog.getByRole('button', { name: '취소' }).click()
  expect(taskCount()).toBe(before) // none of the refused uploads left a task behind
})

// ===================== 5. a document from the real AI (the only call to Gemini)

test('5. 문서 생성(실제 Gemini): 대기/진행 표시, 완성, 7개 챕터, 개념 카드, 줄별 설명 연동', async ({
  page,
}) => {
  // Nothing queued by the earlier scenarios may reach the AI: finish their documents and empty the queue.
  psql(
    `update learning_documents set generation_status = 'failed', generation_error = '테스트 준비', generation_completed_at = now() where generation_status in ('pending', 'in_progress');`,
  )
  docker('exec', 'codelearning-redis', 'redis-cli', 'del', 'document_generation')
  await startWorker()
  try {
    await login(page, USER_A)
    await openProject(page, '메인 프로젝트')
    await pasteTask(page, 'AI가 만드는 문서', SMALL_CODE)
    await confirmUpload(page)
    await taskList(page).getByText('AI가 만드는 문서').click()
    await expect(page).toHaveURL(/\/tasks\/[0-9a-f-]{36}$/)
    aiTaskUrl = page.url()

    const waiting = page.getByText('문서 생성을 기다리는 중')
    const progress = page.getByRole('progressbar', { name: '문서 생성 진행률' })
    await expect(waiting.or(progress)).toBeVisible({ timeout: 15_000 })
    if (await progress.isVisible())
      await expect(page.getByText(/약 \d+초 남음|곧 완료됩니다/)).toBeVisible()

    const viewer = page.getByRole('region', { name: '학습 문서' })
    await expect(viewer).toBeVisible({ timeout: 150_000 }) // appears without a reload
    await expect(progress).toHaveCount(0)

    const nav = page.getByRole('navigation', { name: '챕터 탐색' })
    await expect(nav.getByRole('button')).toHaveCount(7)
    await expect(nav.getByRole('button', { name: /^1장/ })).toHaveAttribute('aria-current', 'true')
    for (let n = 1; n <= 7; n++) {
      await nav.getByRole('button', { name: new RegExp(`^${n}장`) }).click()
      await expect(nav.getByRole('button', { name: new RegExp(`^${n}장`) })).toHaveAttribute(
        'aria-current',
        'true',
      )
      await expect(page.getByRole('region', { name: '챕터 내용' })).not.toBeEmpty()
    }

    await nav.getByRole('button', { name: /^2장/ }).click()
    const cards = page.getByRole('region', { name: '챕터 내용' }).getByRole('listitem')
    expect(await cards.count()).toBeGreaterThan(0)
    expect(await cards.count()).toBeLessThanOrEqual(5)
    expect(
      await page
        .getByRole('region', { name: '챕터 내용' })
        .getByText('비유', { exact: true })
        .count(),
    ).toBe(await cards.count())

    await nav.getByRole('button', { name: /^4장/ }).click()
    await expect(editorOf(page)).toBeVisible({ timeout: 30_000 })
    await page
      .getByRole('button', { name: /코드에서 보기$/ })
      .first()
      .click()
    await expect(editorOf(page).locator('.code-highlight-line').first()).toBeVisible()

    const taskId = aiTaskUrl.split('/').pop()
    const doc = await (await page.request.get(`${API}/tasks/${taskId}/document`)).json()
    expect(doc.status).toBe('completed')
    expect(Object.keys(doc.content)).toEqual([
      'chapter1',
      'chapter2',
      'chapter3',
      'chapter4',
      'chapter5',
      'chapter6',
      'chapter7',
    ])
    expect(
      psql(`select generation_status from learning_documents where task_id = '${taskId}';`),
    ).toBe('completed')
  } finally {
    stopWorker()
  }
})

// ============================ 5b. the viewer with a document written by hand

test('5b. 문서 화면: 나란히 보기, 설명 ↔ 코드 연동, 스크롤 동기화 (AI 호출 없음)', async ({
  page,
}) => {
  const externalHosts = new Set<string>()
  const consoleErrors: string[] = []
  await login(page, USER_A)
  page.on('request', (request) => {
    const url = new URL(request.url())
    if (!['localhost', '127.0.0.1'].includes(url.hostname) && url.protocol.startsWith('http'))
      externalHosts.add(url.hostname)
  })
  page.on('console', (message) => {
    if (message.type() === 'error') consoleErrors.push(message.text())
  })
  page.on('pageerror', (error) => consoleErrors.push(`pageerror: ${error.message}`))

  const id = await apiUpload(page.request, projectMain, '손으로 만든 문서', LONG_CODE)
  seededTaskUrl = `/tasks/${id}`
  psql(
    `update learning_documents set content = $json$${JSON.stringify(handMadeDocument())}$json$::jsonb, ` +
      `generation_status = 'completed', generation_started_at = now(), generation_completed_at = now() where task_id = '${id}';`,
  )
  await page.goto(seededTaskUrl)
  await expect(page.getByRole('region', { name: '학습 문서' })).toBeVisible({ timeout: 20_000 })
  const editor = editorOf(page)
  await expect(editor).toBeVisible({ timeout: 30_000 })
  await expect(editor.locator('.view-lines')).toContainText('def grade_1(score):')
  await expect(editor.locator('.line-numbers').first()).toHaveText('1')
  expect(await editor.locator('.view-line span span[class*="mtk"]').count()).toBeGreaterThan(10) // syntax colours
  await editor.click()
  await page.keyboard.type('HACKED')
  await expect(editor.locator('.view-lines')).not.toContainText('HACKED') // read only

  const code = await editor.boundingBox()
  const notes = await page.getByRole('region', { name: '챕터 내용' }).boundingBox()
  expect(code && notes && Math.abs(code.y - notes.y) < 120 && code.x !== notes.x).toBe(true) // side by side

  await page
    .getByRole('navigation', { name: '챕터 탐색' })
    .getByRole('button', { name: /^2장/ })
    .click()
  await expect(
    page.getByRole('region', { name: '챕터 내용' }).getByRole('listitem', { name: '개념1' }),
  ).toBeVisible()
  await expect(page.getByText('두 번째 줄입니다.').first()).toBeVisible()

  await page
    .getByRole('navigation', { name: '챕터 탐색' })
    .getByRole('button', { name: /^4장/ })
    .click()
  await expect.poll(async () => Math.min(...(await visibleNumbers(page)))).toBe(1)
  for (const { s, e } of [ENTRIES[3], ENTRIES[4], ENTRIES[1]]) {
    await page.getByRole('button', { name: `${FILE} ${label(s, e)} 코드에서 보기` }).click()
    await expect.poll(async () => (await visibleNumbers(page)).includes(s)).toBe(true)
    const rows = await editor.locator('.code-highlight-line').count()
    expect(rows).toBeGreaterThan(0)
    expect(rows).toBeLessThanOrEqual(e - s + 1)
  }

  await editor.hover()
  const active = page
    .getByRole('region', { name: '챕터 내용' })
    .locator('button[aria-current="true"]')
  const followed: string[] = []
  for (let step = 1; step <= 5; step++) {
    await page.mouse.wheel(0, 450)
    await page.waitForTimeout(700)
    const top = Math.min(...(await visibleNumbers(page)))
    const covering = ENTRIES.find((x) => x.s <= top && top <= x.e)
    if (covering) {
      await expect(active).toHaveAttribute(
        'aria-label',
        `${FILE} ${label(covering.s, covering.e)} 코드에서 보기`,
      )
      followed.push(label(covering.s, covering.e))
    }
  }
  expect(followed.length).toBeGreaterThanOrEqual(1) // the entry followed the code at least once
  for (let i = 0; i < 8; i++) {
    await page.mouse.wheel(0, -450)
    await page.waitForTimeout(250)
  }
  await page.waitForTimeout(1200)
  expect(Math.min(...(await visibleNumbers(page)))).toBe(1) // back at the top, no endless chasing

  consoleErrors.length = 0 // (401s of the sign-in check before login are normal)
  await page.reload()
  await expect(editorOf(page)).toBeVisible({ timeout: 30_000 })
  expect([...externalHosts]).toEqual([]) // nothing is loaded from a CDN
  expect(consoleErrors).toEqual([])
})

// ========================================================= 6. a failed document

test('6. 문서 생성 실패 경로: 오류 문구가 보이고 화면이 무너지지 않는다', async ({ page }) => {
  await login(page, USER_A)
  const id = await apiUpload(page.request, projectMain, '실패한 문서', SMALL_CODE)
  const message =
    '문서를 만드는 데 너무 오래 걸려 중단되었습니다. 더 작은 코드 파일로 다시 업로드하거나 고객지원에 문의하세요.'
  psql(
    `update learning_documents set generation_status = 'failed', generation_error = '${message}', generation_completed_at = now() where task_id = '${id}';`,
  )
  await page.goto(`/tasks/${id}`)
  await expect(page.getByRole('alert').filter({ hasText: message })).toBeVisible()
  await expect(page.getByRole('progressbar')).toHaveCount(0)
  await expect(page.getByRole('region', { name: '학습 문서' })).toHaveCount(0)
  await expect(page.getByRole('tab', { name: '연습문제' })).toBeVisible() // the rest of the page still works
  await expect(page.getByRole('heading', { name: '실패한 문서' })).toBeVisible()
})

// ================================================== 7. who can see what

test('7. 권한과 격리: 계정 B는 A의 프로젝트·Task·문서에 접근할 수 없다', async ({ page }) => {
  await login(page, USER_B)
  await expect(page.getByText('아직 프로젝트가 없습니다.')).toBeVisible()
  await expect(page.getByText('메인 프로젝트')).toHaveCount(0)

  await page.goto(`/projects/${projectMain}`)
  await expect(page.getByRole('alert')).toContainText('이 프로젝트에 접근할 권한이 없습니다.')
  await page.goto(`/tasks/${taskIds.file}`)
  await expect(page.getByRole('alert')).toContainText('이 Task에 접근할 권한이 없습니다.')
  await expect(page.getByRole('link', { name: /대시보드로 돌아가기/ })).toBeVisible()

  const idOfSeeded = seededTaskUrl.split('/').pop()
  for (const path of [
    `/tasks/${idOfSeeded}`,
    `/tasks/${idOfSeeded}/document`,
    `/tasks/${idOfSeeded}/document/status`,
    `/tasks/${idOfSeeded}/code`,
  ]) {
    const response = await page.request.get(`${API}${path}`)
    expect(response.status(), path).toBe(403)
    expect((await response.json()).error).toBe('task_forbidden')
  }
  expect((await page.request.delete(`${API}/tasks/${idOfSeeded}`)).status()).toBe(403)
  expect(
    (
      await page.request.patch(`${API}/tasks/${idOfSeeded}`, { data: { title: '해킹 시도입니다' } })
    ).status(),
  ).toBe(403)
  expect((await page.request.get(`${API}/projects/${projectMain}/tasks`)).status()).toBe(403)

  // Nothing of A's changed, and the trashed project's task is gone for everybody.
  expect(psql(`select title from tasks where id = '${idOfSeeded}';`)).toBe('손으로 만든 문서')
  expect((await page.request.get(`${API}/tasks/${trashedTaskId}`)).status()).toBe(404)
  expect(trashedProjectTitle).toBe('삭제할 프로젝트')
})

// ================================================== 8. what is not built yet

test('8. 아직 없는 기능: 연습문제·Q&A 탭, 휴지통, 없는 주소', async ({ page }) => {
  await login(page, USER_A)
  await page.goto(seededTaskUrl)
  for (const [tab, text] of [
    ['연습문제', '연습문제 기능은 준비 중입니다.'],
    ['Q&A', 'Q&A 기능은 준비 중입니다.'],
  ] as const) {
    await page.getByRole('tab', { name: tab }).click()
    await expect(page.getByText(text)).toBeVisible()
  }
  await page.getByRole('link', { name: '휴지통' }).click()
  await expect(page).toHaveURL(/\/trash$/)
  await expect(page.getByRole('heading', { name: '휴지통' })).toBeVisible()
  await page.goto('/nowhere')
  await expect(page.getByRole('heading', { name: '페이지를 찾을 수 없습니다' })).toBeVisible()
  test.info().annotations.push({
    type: '관찰',
    description:
      '프로젝트 삭제 대화상자는 "휴지통으로 이동… 복구할 수 있습니다"라고 안내하지만 휴지통 화면은 아직 제목뿐이라 복구할 방법이 없다(Phase 10).',
  })
})

// ================================================================ 9. failures

test('9. 오류 상황: 네트워크 실패 복구, Redis가 꺼진 상태의 업로드', async ({ page }) => {
  await login(page, USER_A)

  // 9.1 the API cannot be reached: the dashboard says so, and works again after "다시 시도".
  await page.route('**/api/v1/projects', (route) => route.abort())
  await page.goto('/')
  await expect(page.getByRole('alert')).toBeVisible()
  await expect(page.getByRole('button', { name: '다시 시도' })).toBeVisible()
  await page.unroute('**/api/v1/projects')
  await page.getByRole('button', { name: '다시 시도' }).click()
  await expect(page.getByLabel('프로젝트 목록').getByText('메인 프로젝트')).toBeVisible()

  // 9.2 Redis is down while a task is uploaded: the upload works, the document is marked as failed.
  docker('stop', 'codelearning-redis')
  try {
    const id = await apiUpload(page.request, projectMain, 'Redis가 꺼진 업로드', SMALL_CODE)
    // The enqueue runs after the upload response (background task), so poll for the outcome.
    const readStatus = async () =>
      (await page.request.get(`${API}/tasks/${id}/document/status`)).json()
    await expect.poll(async () => (await readStatus()).status, { timeout: 30_000 }).toBe('failed')
    const status = await readStatus()
    expect(status.error).toBe(
      '문서 생성 요청을 접수하지 못했습니다. 잠시 후 다시 시도하거나 고객지원에 문의하세요.',
    )
    await page.goto(`/tasks/${id}`)
    await expect(
      page.getByRole('alert').filter({ hasText: '문서 생성 요청을 접수하지 못했습니다.' }),
    ).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Redis가 꺼진 업로드' })).toBeVisible()
  } finally {
    docker('start', 'codelearning-redis')
  }
})

// =========================================== 10. small screens and the keyboard

test('10. 반응형과 키보드: 390px 폭의 문서 화면, 챕터 이동, 모달 조작', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page, USER_A)
  await page.goto(seededTaskUrl)
  await expect(page.getByRole('region', { name: '학습 문서' })).toBeVisible({ timeout: 20_000 })
  const editor = editorOf(page)
  await expect(editor).toBeVisible({ timeout: 30_000 })
  const code = await editor.boundingBox()
  const notes = await page.getByRole('region', { name: '챕터 내용' }).boundingBox()
  expect(code && notes && notes.y >= code.y + code.height - 8).toBe(true) // stacked: code above, explanation below
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  )
  expect(overflow).toBeLessThanOrEqual(1) // no sideways scrolling of the page

  // The chapter bar works from the keyboard.
  const third = page
    .getByRole('navigation', { name: '챕터 탐색' })
    .getByRole('button', { name: /^3장/ })
  await third.focus()
  await page.keyboard.press('Enter')
  await expect(third).toHaveAttribute('aria-current', 'true')

  // A dialog opens with Enter and closes with Escape.
  await page.goto('/')
  await page.getByRole('button', { name: '새 프로젝트' }).first().focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('dialog')).toBeVisible()
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toBeHidden()
})
