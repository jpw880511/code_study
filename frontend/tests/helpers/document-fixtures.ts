import type {
  DocumentContent,
  DocumentStatusInfo,
  TaskDocument,
} from '../../src/services/document-service'
import type { TaskCode, TaskCodeFile } from '../../src/services/task-service'

export function makeStatus(overrides: Partial<DocumentStatusInfo> = {}): DocumentStatusInfo {
  return {
    status: 'completed',
    generation_started_at: '2026-11-18T09:00:00Z',
    generation_completed_at: '2026-11-18T09:00:20Z',
    elapsed_seconds: null,
    estimated_total_seconds: null,
    notice: null,
    error: null,
    ...overrides,
  }
}

export function makeContent(overrides: Partial<DocumentContent> = {}): DocumentContent {
  return {
    chapter1: { title: '이 코드가 하는 일', summary: '두 수를 더하는 계산기입니다.' },
    chapter2: {
      title: '미리 알아야 할 지식',
      concepts: [
        {
          name: '함수',
          explanation: '이름을 붙인 코드 묶음입니다.',
          analogy: '요리 레시피와 같습니다.',
          example: 'def add(a, b): return a + b',
          use_cases: '반복 작업을 줄이고, 같은 코드를 다시 쓸 때 사용합니다.',
        },
      ],
    },
    chapter3: {
      title: '코드 구조 한눈에 보기',
      flowchart: 'main -> add -> 출력',
      file_breakdown: { 'calc.py': '계산 함수를 모아 둔 파일' },
    },
    chapter4: {
      title: '한 줄씩 설명',
      explanations: [
        {
          file: 'calc.py',
          line_start: 1,
          line_end: 2,
          code: 'def add(a, b):\n    return a + b',
          what_it_does: '두 수를 더해 돌려줍니다.',
          syntax_breakdown: 'def 는 함수를 정의합니다.',
          analogy: '계산기의 더하기 버튼',
          alternatives: 'sum([a, b]) 도 가능합니다.',
          notes: '',
        },
        {
          file: 'calc.py',
          line_start: 4,
          line_end: 5,
          code: 'print(add(1, 2))',
          what_it_does: '결과를 화면에 출력합니다.',
          syntax_breakdown: '',
          analogy: '',
          alternatives: '',
          notes: '',
        },
      ],
    },
    chapter5: {
      title: '실행 흐름 따라가기',
      steps: [
        { step: 1, description: 'add 함수를 호출합니다.', data: 'a=1, b=2' },
        { step: 2, description: '결과를 출력합니다.', data: '' },
      ],
    },
    chapter6: {
      title: '핵심 개념 정리',
      concepts: [
        {
          name: '반환값',
          what_it_is: '함수가 돌려주는 값',
          why_its_used: '결과를 다른 곳에서 쓰려고',
          where_its_applied: 'add 함수의 return',
        },
      ],
    },
    chapter7: {
      title: '흔한 실수',
      mistakes: [
        {
          wrong: 'return 을 빼먹기',
          right: 'return a + b',
          why: '값이 None 이 됩니다.',
          fix: 'return 을 추가하세요.',
        },
      ],
    },
    ...overrides,
  }
}

export function makeDocument(overrides: Partial<TaskDocument> = {}): TaskDocument {
  return {
    task_id: 't-1',
    status: 'completed',
    content: makeContent(),
    generation_started_at: '2026-11-18T09:00:00Z',
    generation_completed_at: '2026-11-18T09:00:20Z',
    error: null,
    created_at: '2026-11-18T09:00:00Z',
    updated_at: '2026-11-18T09:00:20Z',
    ...overrides,
  }
}

export function makeTaskCodeFile(overrides: Partial<TaskCodeFile> = {}): TaskCodeFile {
  return {
    id: 'f-1',
    file_name: 'calc.py',
    file_path: null,
    file_extension: '.py',
    file_size_bytes: 80,
    mime_type: 'text/x-python',
    language: 'python',
    content: 'def add(a, b):\n    return a + b\n\nprint(add(1, 2))\nprint("끝")\n',
    ...overrides,
  }
}

export function makeTaskCode(files: TaskCodeFile[] = [makeTaskCodeFile()]): TaskCode {
  return { files }
}
