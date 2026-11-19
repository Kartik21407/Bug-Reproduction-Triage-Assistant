// Queries and mutations for duplicate candidates: the stored candidates,
// running a fresh search (US-20), and a person's decision on one (US-21).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { generatedReportKeys } from '@/hooks/useGeneratedReport';
import type { DuplicateDecision, DuplicatesRead } from '@/types/api';

export const duplicateKeys = {
  read: (reportId: string) => ['duplicates', reportId] as const,
};

function afterChange(
  queryClient: ReturnType<typeof useQueryClient>,
  reportId: string,
  result: DuplicatesRead,
) {
  queryClient.setQueryData(duplicateKeys.read(reportId), result);
  queryClient.invalidateQueries({ queryKey: generatedReportKeys.read(reportId) });
  queryClient.invalidateQueries({ queryKey: generatedReportKeys.markdown(reportId) });
  queryClient.invalidateQueries({ queryKey: ['github', 'preview', reportId] });
}

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
    onSuccess: (result) => afterChange(queryClient, reportId, result),
  });
}

export function useDecideDuplicate(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      candidateId,
      decision,
    }: {
      candidateId: string;
      decision: DuplicateDecision | null;
    }) =>
      api.put<DuplicatesRead>(`/reports/${reportId}/duplicates/${candidateId}/decision`, {
        decision,
      }),
    onSuccess: (result) => afterChange(queryClient, reportId, result),
  });
}
