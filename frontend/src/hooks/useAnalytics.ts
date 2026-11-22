// The dashboard's numbers (US-29): the signed-in user's own reports by
// severity, by category and by week; and the fields most often missing
// (US-30).

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AnalyticsRead, MissingFieldsRead } from '@/types/api';

export const analyticsKeys = {
  read: ['analytics'] as const,
  missing: ['analytics', 'missing-fields'] as const,
};

export function useAnalytics() {
  return useQuery({
    queryKey: analyticsKeys.read,
    queryFn: () => api.get<AnalyticsRead>('/analytics'),
  });
}

export function useMissingFields() {
  return useQuery({
    queryKey: analyticsKeys.missing,
    queryFn: () => api.get<MissingFieldsRead>('/analytics/missing-fields'),
  });
}
