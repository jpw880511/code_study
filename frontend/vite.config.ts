import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./tests/setup.ts'],
    include: ['tests/**/*.test.{ts,tsx}', 'src/**/*.test.{ts,tsx}'],
    coverage: {
      provider: 'v8',
      include: ['src/**/*.{ts,tsx}'],
      // monaco-runtime.ts only loads the real Monaco (and its worker), which jsdom cannot run; tests
      // replace it with a fake and it was checked once in a real browser (see TASK-099 report).
      exclude: [
        'src/main.tsx',
        'src/**/*.test.{ts,tsx}',
        'src/components/document/monaco-runtime.ts',
      ],
    },
  },
})
