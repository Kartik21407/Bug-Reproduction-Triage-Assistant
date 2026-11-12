// Queries and mutations for duplicate candidates (US-20): the stored
// candidates, and running a fresh search.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { generatedReportKeys } from '@/hooks/useGeneratedReport';
import type { DuplicatesRead } from '@/types/api';

export const duplicateKeys = {
  read: (reportId: string) => ['duplicates', reportId] as const,
};

export function useDuplicates(reportId: string) {
  return useQuery({
    queryKey: duplicateKeys.read(reportId),
    queryFn: () => api.get<DuplicatesRead>(`/reports/${reportId}/duplicates`),
    enabled: Boolean(reportId),
  });
}

export function useFindDuplicates(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<DuplicatesRead>(`/reports/${reportId}/duplicates`),
    onSuccess: (result) => {
      queryClient.setQueryData(duplicateKeys.read(reportId), result);
      queryClient.invalidateQueries({ queryKey: generatedReportKeys.read(reportId) });
    },
  });
}
