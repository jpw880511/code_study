import { defineConfig } from '@playwright/test'
import { BACKEND_DIR, PYTHON, UPLOAD_DIR } from './e2e/full-flow.env'

// The whole product flow in one run. Unlike the default config it starts the API server and the
// frontend itself (and removes the uploaded files afterwards). It needs Docker's Postgres and
// Redis; the spec starts and stops the Celery worker, because only one scenario may reach Gemini.
//   npm run test:e2e:full
export default defineConfig({
  testDir: './e2e',
  testMatch: 'full-flow.spec.ts',
  workers: 1,
  fullyParallel: false,
  timeout: 180_000,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  // Outside the frontend folder: Vite watches it and reloads the page whenever a trace is written.
  outputDir: '../.playwright-results',
  globalTeardown: './e2e/full-flow.teardown.ts',
  webServer: [
    {
      command: `"${PYTHON}" -m uvicorn src.main:app --port 8000`,
      cwd: BACKEND_DIR,
      env: { UPLOAD_STORAGE_PATH: UPLOAD_DIR },
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:5173',
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
})
