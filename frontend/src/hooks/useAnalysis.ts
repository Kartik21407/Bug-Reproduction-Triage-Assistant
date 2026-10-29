// Queries and mutations for the analysis pipeline: masking preview (US-32),
// running analysis, reading the persisted result with the completeness
// score (US-13), answering a follow-up question (US-14), and environment
// review (US-33).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { reportKeys } from '@/hooks/useReports';
import type {
  AnalysisRead,
  AnalyzeRequest,
  AnalyzeResult,
  AnswerQuestionRequest,
  EnvironmentReviewRequest,
  MaskingResult,
} from '@/types/api';

export const analysisKeys = {
  mask: (reportId: string) => ['analysis', 'mask', reportId] as const,
  read: (reportId: string) => ['analysis', 'read', reportId] as const,
};

// Invalidated after analyze, answer or environment review, since all three
// can change the report's title or state as shown on ReportDetail and
// History.
function invalidateReport(queryClient: ReturnType<typeof useQueryClient>, reportId: string) {
  queryClient.invalidateQueries({ queryKey: reportKeys.detail(reportId) });
  queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
}

export function useMaskPreview(reportId: string) {
  return useQuery({
    queryKey: analysisKeys.mask(reportId),
    queryFn: () => api.post<MaskingResult>(`/reports/${reportId}/mask`),
    enabled: Boolean(reportId),
  });
}

export function useAnalyzeReport(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AnalyzeRequest) =>
      api.post<AnalyzeResult>(`/reports/${reportId}/analyze`, body),
    onSuccess: () => {
      // The analyze response does not carry the completeness score;
      // invalidate rather than guess it, so the next read recomputes it.
      queryClient.invalidateQueries({ queryKey: analysisKeys.read(reportId) });
      invalidateReport(queryClient, reportId);
    },
  });
}

export function useAnalysisRead(reportId: string) {
  return useQuery({
    queryKey: analysisKeys.read(reportId),
    queryFn: () => api.get<AnalysisRead>(`/reports/${reportId}/analysis`),
    enabled: Boolean(reportId),
  });
}

export function useAnswerQuestion(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ questionId, answer }: { questionId: string; answer: string }) =>
      api.post<AnalysisRead>(`/reports/${reportId}/questions/${questionId}/answer`, {
        answer,
      } satisfies AnswerQuestionRequest),
    onSuccess: (result) => {
      queryClient.setQueryData(analysisKeys.read(reportId), result);
      invalidateReport(queryClient, reportId);
    },
  });
}

export function useReviewEnvironment(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: EnvironmentReviewRequest) =>
      api.post<AnalysisRead>(`/reports/${reportId}/environment`, body),
    onSuccess: (result) => {
      queryClient.setQueryData(analysisKeys.read(reportId), result);
      invalidateReport(queryClient, reportId);
    },
  });
}
