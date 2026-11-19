// The fixed-template report for one report (US-23), editing and resetting
// its fields (US-24), its Markdown (US-25), and marking it reviewed or
// exported (DR-10). All of it is assembled on the server.

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { reportKeys } from '@/hooks/useReports';
import type {
  EditableField,
  GeneratedReport,
  MarkdownRead,
  ReportEditRequest,
  ReportRead,
} from '@/types/api';

export const generatedReportKeys = {
  read: (reportId: string) => ['generated-report', reportId] as const,
  markdown: (reportId: string) => ['generated-report', 'markdown', reportId] as const,
};

export function useGeneratedReport(reportId: string) {
  return useQuery({
    queryKey: generatedReportKeys.read(reportId),
    queryFn: () => api.get<GeneratedReport>(`/reports/${reportId}/report`),
    enabled: Boolean(reportId),
  });
}

export function useMarkdown(reportId: string, { enabled = true }: { enabled?: boolean } = {}) {
  return useQuery({
    queryKey: generatedReportKeys.markdown(reportId),
    queryFn: () => api.get<MarkdownRead>(`/reports/${reportId}/markdown`),
    enabled: Boolean(reportId) && enabled,
  });
}

// An edit or a reset changes the report, its Markdown, and possibly its
// title and triage, which the analysis, triage and report pages all show.
function afterChange(queryClient: ReturnType<typeof useQueryClient>, reportId: string) {
  queryClient.invalidateQueries({ queryKey: generatedReportKeys.markdown(reportId) });
  queryClient.invalidateQueries({ queryKey: ['analysis', 'read', reportId] });
  queryClient.invalidateQueries({ queryKey: ['triage', reportId] });
  queryClient.invalidateQueries({ queryKey: reportKeys.detail(reportId) });
  queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
}

export function useEditReport(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ReportEditRequest) =>
      api.patch<GeneratedReport>(`/reports/${reportId}/report`, body),
    onSuccess: (result) => {
      queryClient.setQueryData(generatedReportKeys.read(reportId), result);
      afterChange(queryClient, reportId);
    },
  });
}

export function useResetReportField(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (field: EditableField) =>
      api.delete<GeneratedReport>(`/reports/${reportId}/report/fields/${field}`),
    onSuccess: (result) => {
      queryClient.setQueryData(generatedReportKeys.read(reportId), result);
      afterChange(queryClient, reportId);
    },
  });
}

function useMoveState(reportId: string, action: 'review' | 'export') {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<ReportRead>(`/reports/${reportId}/${action}`),
    onSuccess: (report) => {
      queryClient.setQueryData(reportKeys.detail(reportId), report);
      queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
    },
  });
}

export function useMarkReviewed(reportId: string) {
  return useMoveState(reportId, 'review');
}

export function useMarkExported(reportId: string) {
  return useMoveState(reportId, 'export');
}
