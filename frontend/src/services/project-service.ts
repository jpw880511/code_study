import { apiClient } from './api-client'

// Thin typed wrappers over the /projects endpoints. No store or React access here.

export interface Project {
  id: string
  title: string
  description: string | null
  created_at: string
  updated_at: string
  last_activity_at: string
}

export interface CreateProjectInput {
  title: string
  description?: string
}

// Partial update: only the keys present are sent; an explicit null description clears it.
export interface UpdateProjectInput {
  title?: string
  description?: string | null
}

export async function listProjects(): Promise<Project[]> {
  const { data } = await apiClient.get<Project[]>('/projects')
  return data
}

export async function createProject(input: CreateProjectInput): Promise<Project> {
  const { data } = await apiClient.post<Project>('/projects', input)
  return data
}

export async function getProject(id: string): Promise<Project> {
  const { data } = await apiClient.get<Project>(`/projects/${id}`)
  return data
}

export async function updateProject(id: string, input: UpdateProjectInput): Promise<Project> {
  const { data } = await apiClient.patch<Project>(`/projects/${id}`, input)
  return data
}

export async function deleteProject(id: string): Promise<void> {
  await apiClient.delete(`/projects/${id}`)
}
