import * as monaco from 'monaco-editor/editor/editor.api'
import 'monaco-editor/languages/definitions/register.all'
import EditorWorker from 'monaco-editor/editor/editor.worker?worker'

// The only module that loads Monaco. Everything is bundled (no CDN), and the only worker
// needed for a read-only viewer is the base editor worker, bundled through Vite's ?worker.
// Basic syntax highlighting is registered for all languages; each tokenizer loads on demand.
self.MonacoEnvironment = { getWorker: () => new EditorWorker() }

const ALIASES: Record<string, string> = {
  'c++': 'cpp',
  c: 'cpp',
  'c#': 'csharp',
  js: 'javascript',
  jsx: 'javascript',
  ts: 'typescript',
  tsx: 'typescript',
  py: 'python',
  sh: 'shell',
  bash: 'shell',
  rb: 'ruby',
  rs: 'rust',
  kt: 'kotlin',
  yml: 'yaml',
}

// The language names the server detects are mapped to Monaco's ids; unknown ones are plain text.
export function monacoLanguageId(language: string): string {
  const name = language.trim().toLowerCase()
  const id = ALIASES[name] ?? name
  return monaco.languages.getLanguages().some((known) => known.id === id) ? id : 'plaintext'
}

export { monaco }
