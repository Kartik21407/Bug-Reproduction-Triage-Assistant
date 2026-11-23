// Queries and mutations for the administrator page: accounts (US-03), the
// duplicate thresholds (US-31) and the automatic corpus import (US-28).
// Every endpoint answers 403 to anyone who is not an administrator.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AdminUser, CorpusSyncRead, DuplicateThresholds } from '@/types/api';

export const adminKeys = {
  users: ['admin', 'users'] as const,
  thresholds: ['admin', 'thresholds'] as const,
  corpusSync: ['admin', 'corpus-sync'] as const,
};

export function useAdminUsers() {
  return useQuery({
    queryKey: adminKeys.users,
    queryFn: () => api.get<AdminUser[]>('/admin/users'),
  });
}

export function useSetUserActive() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ userId, isActive }: { userId: string; isActive: boolean }) =>
      api.patch<AdminUser>(`/admin/users/${userId}`, { is_active: isActive }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.users }),
  });
}

export function useThresholds() {
  return useQuery({
    queryKey: adminKeys.thresholds,
    queryFn: () => api.get<DuplicateThresholds>('/admin/settings/duplicate-thresholds'),
  });
}

export function useSaveThresholds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { likely: number; possible: number }) =>
      api.put<DuplicateThresholds>('/admin/settings/duplicate-thresholds', body),
    onSuccess: (result) => queryClient.setQueryData(adminKeys.thresholds, result),
  });
}

export function useResetThresholds() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<DuplicateThresholds>('/admin/settings/duplicate-thresholds'),
    onSuccess: (result) => queryClient.setQueryData(adminKeys.thresholds, result),
  });
}

// While an import runs, the page polls for progress every few seconds.
export function useCorpusSync() {
  return useQuery({
    queryKey: adminKeys.corpusSync,
    queryFn: () => api.get<CorpusSyncRead>('/admin/corpus-sync'),
    refetchInterval: (query) =>
      query.state.data?.running || query.state.data?.state?.status === 'running' ? 3000 : false,
  });
}

export function useSaveSyncRepository() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (repository: string) =>
      api.put<CorpusSyncRead>('/admin/corpus-sync', { repository }),
    onSuccess: (result) => queryClient.setQueryData(adminKeys.corpusSync, result),
  });
}

export function useRunSync() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>('/admin/corpus-sync/run'),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: adminKeys.corpusSync }),
  });
}
