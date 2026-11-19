// Monaco's package maps "monaco-editor/<path>" to its ESM files, which ship no typings of their
// own. The editor core and the language registrations are imported by path so that only what is
// needed is bundled (not the language services and their workers), and typed through the package.
declare module 'monaco-editor/editor/editor.api' {
  export * from 'monaco-editor'
}

declare module 'monaco-editor/languages/definitions/register.all'

declare module 'monaco-editor/editor/editor.worker?worker' {
  const WorkerFactory: new () => Worker
  export default WorkerFactory
}
