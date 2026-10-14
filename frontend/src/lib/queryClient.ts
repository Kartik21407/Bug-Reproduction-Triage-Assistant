// The shared TanStack Query client. A 401 means the session ended, so it is
// not worth retrying; other failures get one retry.

import { QueryClient } from '@tanstack/react-query';
import { ApiRequestError } from '@/lib/api';

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: (failureCount, error) => {
        if (error instanceof ApiRequestError && error.status === 401) return false;
        return failureCount < 1;
      },
      staleTime: 30_000,
    },
    mutations: {
      retry: false,
    },
  },
});
