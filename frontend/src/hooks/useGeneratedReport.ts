// The fixed-template report for one report (US-23), assembled by the server
// from the stored analysis, triage and duplicate candidates.

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { GeneratedReport } from '@/types/api';

export const generatedReportKeys = {
  read: (reportId: string) => ['generated-report', reportId] as const,
};

export function useGeneratedReport(reportId: string) {
  return useQuery({
    queryKey: generatedReportKeys.read(reportId),
    queryFn: () => api.get<GeneratedReport>(`/reports/${reportId}/report`),
    enabled: Boolean(reportId),
  });
}
