import type { Project } from '../../src/services/project-service'

export function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'p-1',
    title: '알고리즘 스터디',
    description: '정렬 알고리즘을 분석합니다.',
    created_at: '2026-11-01T12:00:00Z',
    updated_at: '2026-11-02T12:00:00Z',
    last_activity_at: '2026-11-03T12:00:00Z',
    ...overrides,
  }
}
