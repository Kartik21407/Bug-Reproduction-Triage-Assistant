// Queries and mutations for the user's own reports: create (US-04, US-05),
// list with search and filters (US-06), read by id, update and delete
// (US-07).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  ReportCreate,
  ReportListResponse,
  ReportRead,
  ReportState,
  ReportUpdate,
  Severity,
} from '@/types/api';

export interface ReportListFilters {
  search?: string;
  severity?: Severity;
  state?: ReportState;
}

export const reportKeys = {
  list: (filters: ReportListFilters = {}) => ['reports', 'list', filters] as const,
  detail: (id: string) => ['reports', 'detail', id] as const,
};

function invalidateReportLists(queryClient: ReturnType<typeof useQueryClient>) {
  // Matches every list query regardless of its filters (US-06), since a
  // create, edit or delete could change which list a report belongs in.
  queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
}

export function useCreateReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ReportCreate) => api.post<ReportRead>('/reports', body),
    onSuccess: () => invalidateReportLists(queryClient),
  });
}

function buildQueryString(filters: ReportListFilters): string {
  const params = new URLSearchParams();
  if (filters.search?.trim()) params.set('search', filters.search.trim());
  if (filters.severity) params.set('severity', filters.severity);
  if (filters.state) params.set('state', filters.state);
  const query = params.toString();
  return query ? `?${query}` : '';
}

export function useReportsList(filters: ReportListFilters) {
  return useQuery({
    queryKey: reportKeys.list(filters),
    queryFn: () => api.get<ReportListResponse>(`/reports${buildQueryString(filters)}`),
  });
}

export function useReport(id: string) {
  return useQuery({
    queryKey: reportKeys.detail(id),
    queryFn: () => api.get<ReportRead>(`/reports/${id}`),
    enabled: Boolean(id),
  });
}

export function useUpdateReport(id: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: ReportUpdate) => api.patch<ReportRead>(`/reports/${id}`, body),
    onSuccess: (report) => {
      queryClient.setQueryData(reportKeys.detail(id), report);
      invalidateReportLists(queryClient);
    },
  });
}

export function useDeleteReport() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.delete<void>(`/reports/${id}`),
    onSuccess: (_data, id) => {
      queryClient.removeQueries({ queryKey: reportKeys.detail(id) });
      invalidateReportLists(queryClient);
    },
  });
}
