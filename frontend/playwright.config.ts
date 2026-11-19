import { defineConfig } from '@playwright/test'

// E2E runs against the already running dev servers (frontend 5173, backend 8000).
export default defineConfig({
  testDir: './e2e',
  // The full-flow spec needs its own servers and worker: see playwright.full-flow.config.ts.
  testIgnore: 'full-flow.spec.ts',
  workers: 1,
  fullyParallel: false,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  // Outside the frontend folder: Vite watches it and reloads the page whenever a trace is written.
  outputDir: '../.playwright-results',
})
