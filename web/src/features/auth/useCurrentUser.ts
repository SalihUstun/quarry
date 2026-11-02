import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchCurrentUser, logout } from '../../api/client'

export const currentUserKey = ['current-user'] as const

export function useCurrentUser() {
  return useQuery({
    queryKey: currentUserKey,
    queryFn: ({ signal }) => fetchCurrentUser(signal),
    staleTime: Infinity,
  })
}

export function useLogout() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: logout,
    onSuccess: () => {
      queryClient.clear()
      queryClient.setQueryData(currentUserKey, null)
    },
  })
}
