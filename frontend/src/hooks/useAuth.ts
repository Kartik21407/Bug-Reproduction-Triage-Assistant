// Queries and mutations for the current session: register, login, logout,
// current user (US-01).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiRequestError } from '@/lib/api';
import type { UserCreate, UserLogin, UserRead } from '@/types/api';

export const authKeys = {
  me: ['auth', 'me'] as const,
};

/** The signed-in user, or null when there is no session. A 401 is expected
 * and is not treated as a query error. */
export function useCurrentUser() {
  return useQuery({
    queryKey: authKeys.me,
    queryFn: async (): Promise<UserRead | null> => {
      try {
        return await api.get<UserRead>('/auth/me');
      } catch (error) {
        if (error instanceof ApiRequestError && error.status === 401) return null;
        throw error;
      }
    },
  });
}

export function useRegister() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UserCreate) => api.post<UserRead>('/auth/register', body),
    onSuccess: (user) => {
      queryClient.setQueryData(authKeys.me, user);
    },
  });
}

export function useLogin() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: UserLogin) => api.post<UserRead>('/auth/login', body),
    onSuccess: (user) => {
      queryClient.setQueryData(authKeys.me, user);
    },
  });
}

export function useLogout() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>('/auth/logout'),
    onSuccess: () => {
      queryClient.setQueryData(authKeys.me, null);
      queryClient.clear();
    },
  });
}
