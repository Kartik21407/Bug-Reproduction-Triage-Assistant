// GitHub: the connection (never the token, US-26 criterion 3), the
// repositories the token can file issues in, and previewing then filing a
// report as an issue (US-27).

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { reportKeys } from '@/hooks/useReports';
import type { GitHubConnection, GitHubRepository, IssueCreated, IssuePreview } from '@/types/api';

export const githubKeys = {
  connection: ['github', 'connection'] as const,
  repositories: ['github', 'repositories'] as const,
  preview: (reportId: string) => ['github', 'preview', reportId] as const,
};

export function useGithubConnection() {
  return useQuery({
    queryKey: githubKeys.connection,
    queryFn: () => api.get<GitHubConnection>('/github/connection'),
  });
}

export function useConnectGithub() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (token: string) => api.put<GitHubConnection>('/github/connection', { token }),
    onSuccess: (connection) => {
      queryClient.setQueryData(githubKeys.connection, connection);
      queryClient.invalidateQueries({ queryKey: githubKeys.repositories });
    },
  });
}

export function useDisconnectGithub() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => api.delete<void>('/github/connection'),
    onSuccess: () => {
      queryClient.setQueryData(githubKeys.connection, {
        connected: false,
        login: null,
        repository: null,
      } satisfies GitHubConnection);
      queryClient.removeQueries({ queryKey: githubKeys.repositories });
    },
  });
}

export function useGithubRepositories({ enabled }: { enabled: boolean }) {
  return useQuery({
    queryKey: githubKeys.repositories,
    queryFn: () => api.get<GitHubRepository[]>('/github/repositories'),
    enabled,
  });
}

export function useChooseRepository() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (repository: string) =>
      api.put<GitHubConnection>('/github/connection/repository', { repository }),
    onSuccess: (connection) => {
      queryClient.setQueryData(githubKeys.connection, connection);
      queryClient.invalidateQueries({ queryKey: ['github', 'preview'] });
    },
  });
}

export function useIssuePreview(reportId: string) {
  return useQuery({
    queryKey: githubKeys.preview(reportId),
    queryFn: () => api.get<IssuePreview>(`/reports/${reportId}/github/preview`),
    enabled: Boolean(reportId),
  });
}

export function useCreateIssue(reportId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (acknowledgeLikelyDuplicates: boolean) =>
      api.post<IssueCreated>(`/reports/${reportId}/github/issue`, {
        acknowledge_likely_duplicates: acknowledgeLikelyDuplicates,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: githubKeys.preview(reportId) });
      queryClient.invalidateQueries({ queryKey: reportKeys.detail(reportId) });
      queryClient.invalidateQueries({ queryKey: ['reports', 'list'] });
    },
  });
}
