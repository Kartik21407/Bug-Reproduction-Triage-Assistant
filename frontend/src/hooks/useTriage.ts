// Queries and mutations for triage (US-15, US-16, US-17): the four
// suggested values with their reasons, and a person's override.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { reportKeys } from '@/hooks/useReports';
import { generatedReportKeys } from '@/hooks/useGeneratedReport';
import type { TriageOverrideRequest, TriageRead } from '@/types/api';

export const triageKeys = {
  read: (reportId: string) => ['triage', reportId] as const,
};

// `enabled` lets a page wait until it knows the report has been analysed,
// since the server computes triage on its first read.
export function useTriage(reportId: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: triageKeys.read(reportId),
    queryFn: () => api.get<TriageRead>(`/reports/${reportId}/triage`),
    enabled: Boolean(reportId) && enabled,
  });
}

export function useOverrideTriage(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: TriageOverrideRequest) =>
      api.patch<TriageRead>(`/reports/${reportId}/triage`, body),
    onSuccess: (result) => {
      queryClient.setQueryData(triageKeys.read(reportId), result);
      queryClient.invalidateQueries({ queryKey: generatedReportKeys.read(reportId) });
      // Severity is shown on ReportDetail and filtered on in History.
      queryClient.invalidateQueries({ queryKey: reportKeys.detail(reportId) });
      queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
    },
  });
}
