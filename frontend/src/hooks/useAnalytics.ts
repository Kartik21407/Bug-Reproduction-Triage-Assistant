// The dashboard's numbers (US-29): the signed-in user's own reports by
// severity, by category and by week.

import { useQuery } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type { AnalyticsRead } from '@/types/api';

export const analyticsKeys = {
  read: ['analytics'] as const,
};

export function useAnalytics() {
  return useQuery({
    queryKey: analyticsKeys.read,
    queryFn: () => api.get<AnalyticsRead>('/analytics'),
  });
}
