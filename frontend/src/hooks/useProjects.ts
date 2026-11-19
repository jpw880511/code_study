import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import {
  createProject,
  deleteProject,
  getProject,
  listProjects,
  updateProject,
  type UpdateProjectInput,
} from '../services/project-service'

const LIST_KEY = ['projects'] as const
const detailKey = (id: string) => ['projects', id] as const

export function useProjects() {
  return useQuery({ queryKey: LIST_KEY, queryFn: listProjects })
}

export function useProject(id: string) {
  return useQuery({ queryKey: detailKey(id), queryFn: () => getProject(id) })
}

// Mutations wait for the list refetch (returned from onSuccess), so when they resolve the
// UI already shows the fresh data. No optimistic updates: the server is the authority.
export function useCreateProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: createProject,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: LIST_KEY, exact: true }),
  })
}

export function useUpdateProject(id: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: UpdateProjectInput) => updateProject(id, input),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: LIST_KEY, exact: true }),
        queryClient.invalidateQueries({ queryKey: detailKey(id), exact: true }),
      ]),
  })
}

export function useDeleteProject() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: deleteProject,
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: detailKey(id), exact: true })
      return queryClient.invalidateQueries({ queryKey: LIST_KEY, exact: true })
    },
  })
}
