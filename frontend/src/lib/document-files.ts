import type { TaskCodeFile } from '../services/task-service'

// The name a file goes by in the document: its path when it has one, else its name.
export function codeFileKey(file: TaskCodeFile): string {
  return file.file_path ?? file.file_name
}

// A chapter 4 entry names its file by path (or by name when the file has no path).
export function fileMatches(name: string, file: TaskCodeFile): boolean {
  return name === codeFileKey(file) || name === file.file_name
}
