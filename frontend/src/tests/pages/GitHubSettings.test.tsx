import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GitHubSettings from '@/pages/GitHubSettings';
import type { GitHubConnection, GitHubRepository } from '@/types/api';

const TOKEN = 'github_pat_test_only_0123456789abcdef';

const DISCONNECTED: GitHubConnection = { connected: false, login: null, repository: null };
const CONNECTED: GitHubConnection = { connected: true, login: 'octo', repository: null };

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

interface MockOptions {
  connection?: GitHubConnection;
  repositories?: GitHubRepository[];
  onConnect?: (body: { token: string }) => Response;
}

function mockFetch({ connection = DISCONNECTED, repositories = [], onConnect }: MockOptions) {
  const calls: { method: string; path: string; body: unknown }[] = [];
  let current = connection;
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    const path = String(url);
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    calls.push({ method, path, body });
    if (path.endsWith('/github/connection') && method === 'PUT') {
      if (onConnect) return onConnect(body);
      current = { connected: true, login: 'octo', repository: null };
      return jsonResponse(current);
    }
    if (path.endsWith('/github/connection/repository')) {
      current = { ...current, repository: body.repository };
      return jsonResponse(current);
    }
    if (path.endsWith('/github/repositories')) return jsonResponse(repositories);
    return jsonResponse(current);
  });
  return calls;
}

function renderSettings() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <GitHubSettings />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GitHubSettings', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('accepts a token, then shows the account and clears the field', async () => {
    // Arrange
    const calls = mockFetch({});
    renderSettings();
    const user = userEvent.setup();
    const input = await screen.findByLabelText('Fine-grained personal access token');

    // Act
    await user.type(input, TOKEN);
    await user.click(screen.getByRole('button', { name: 'Connect' }));

    // Assert: US-26 criterion 1
    expect(await screen.findByText('octo')).toBeInTheDocument();
    expect(screen.getByLabelText('Replace the token')).toHaveValue('');
    expect(calls).toContainEqual({
      method: 'PUT',
      path: '/api/github/connection',
      body: { token: TOKEN },
    });
  });

  it('keeps the token hidden while it is typed', async () => {
    // Arrange
    mockFetch({});

    // Act
    renderSettings();

    // Assert
    expect(await screen.findByLabelText('Fine-grained personal access token')).toHaveAttribute(
      'type',
      'password',
    );
  });

  it('shows a clear error for a token GitHub does not accept', async () => {
    // Arrange
    const detail =
      'GitHub did not accept this token. Check it was copied in full and has not expired or been revoked.';
    mockFetch({ onConnect: () => jsonResponse({ detail }, 400) });
    renderSettings();
    const user = userEvent.setup();

    // Act
    await user.type(await screen.findByLabelText('Fine-grained personal access token'), 'nope');
    await user.click(screen.getByRole('button', { name: 'Connect' }));

    // Assert: US-26 criterion 2
    expect(await screen.findByText(detail)).toBeInTheDocument();
  });

  it('lists only the repositories the server returns and saves the choice', async () => {
    // Arrange
    const calls = mockFetch({
      connection: CONNECTED,
      repositories: [
        { full_name: 'octo/app', private: false },
        { full_name: 'octo/secret', private: true },
      ],
    });
    renderSettings();
    const user = userEvent.setup();
    const select = await screen.findByLabelText('Repository to file issues in');

    // Act
    await user.selectOptions(select, 'octo/secret');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Assert: US-26 criterion 4
    expect(screen.getAllByRole('option').map((o) => o.textContent)).toEqual([
      'Choose a repository',
      'octo/app',
      'octo/secret (private)',
    ]);
    await waitFor(() =>
      expect(calls).toContainEqual({
        method: 'PUT',
        path: '/api/github/connection/repository',
        body: { repository: 'octo/secret' },
      }),
    );
    expect(await screen.findByText('octo/secret', { selector: 'span' })).toBeInTheDocument();
  });

  it('says so when the token cannot file issues anywhere', async () => {
    // Arrange
    mockFetch({ connection: CONNECTED, repositories: [] });

    // Act
    renderSettings();

    // Assert
    expect(
      await screen.findByText(/This token cannot file issues in any repository yet/),
    ).toBeInTheDocument();
  });
});
