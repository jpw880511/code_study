import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { createTask, getTask, listTasks, type CreateTaskInput } from '../services/task-service'

const listKey = (projectId: string) => ['projects', projectId, 'tasks'] as const
const detailKey = (id: string) => ['tasks', id] as const

export function useTasks(projectId: string) {
  return useQuery({ queryKey: listKey(projectId), queryFn: () => listTasks(projectId) })
}

export function useTask(id: string) {
  return useQuery({ queryKey: detailKey(id), queryFn: () => getTask(id) })
}

// Creating a task also moves the project's last activity, so the project and the project
// list are refreshed too. The mutation waits for the refetches, as with projects.
export function useCreateTask(projectId: string) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (input: CreateTaskInput) => createTask(projectId, input),
    onSuccess: () =>
      Promise.all([
        queryClient.invalidateQueries({ queryKey: listKey(projectId), exact: true }),
        queryClient.invalidateQueries({ queryKey: ['projects', projectId], exact: true }),
        queryClient.invalidateQueries({ queryKey: ['projects'], exact: true }),
      ]),
  })
}
