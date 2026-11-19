import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'

// Shared by the full-flow Playwright config, the spec (which starts and stops the Celery worker)
// and the teardown. Playwright runs from the frontend folder.
export const BACKEND_DIR = resolve(process.cwd(), '..', 'backend')
export const PYTHON = join(BACKEND_DIR, '.venv', 'Scripts', 'python.exe')
// The API server and the worker must read and write the same uploaded files.
export const UPLOAD_DIR = join(tmpdir(), 'code-study-fullflow-uploads')
