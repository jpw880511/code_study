import { rmSync } from 'node:fs'
import { UPLOAD_DIR } from './full-flow.env'

export default function teardown() {
  rmSync(UPLOAD_DIR, { recursive: true, force: true })
}
