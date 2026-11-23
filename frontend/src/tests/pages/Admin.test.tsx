import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Admin from '@/pages/Admin';
import type { AdminUser, CorpusSyncRead, DuplicateThresholds } from '@/types/api';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

const ME = { id: 'a1', email: 'admin@example.com', is_admin: true, created_at: '2026-01-01' };

const USERS: AdminUser[] = [
  { ...ME, is_active: true, report_count: 0 },
  {
    id: 'u2',
    email: 'member@example.com',
    is_admin: false,
    is_active: true,
    report_count: 3,
    created_at: '2026-01-02',
  },
];

const THRESHOLDS: DuplicateThresholds = {
  likely: 0.8,
  possible: 0.6,
  default_likely: 0.8,
  default_possible: 0.6,
  customised: false,
};

const SYNC: CorpusSyncRead = {
  repository: 'acme/app',
  interval_minutes: 60,
  running: false,
  state: {
    repository: 'acme/app',
    status: 'paused',
    pages_done: 2,
    imported: 150,
    updated: 10,
    skipped: 0,
    message: "GitHub's rate limit stopped the import after 2 pages. Nothing was lost.",
    resume_after: null,
    started_at: null,
    finished_at: null,
  },
};

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function mockApi(overrides: { onThresholds?: (body: unknown) => Response } = {}) {
  const calls: Call[] = [];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    const path = String(url);
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    if (method !== 'GET') calls.push({ method, path, body });
    if (path.endsWith('/auth/me')) return jsonResponse(ME);
    if (path.endsWith('/admin/users')) return jsonResponse(USERS);
    if (path.includes('/admin/users/')) {
      return jsonResponse({ ...USERS[1], is_active: (body as { is_active: boolean }).is_active });
    }
    if (path.endsWith('/duplicate-thresholds') && method === 'PUT') {
      return (
        overrides.onThresholds?.(body) ??
        jsonResponse({ ...THRESHOLDS, ...(body as object), customised: true })
      );
    }
    if (path.endsWith('/duplicate-thresholds')) return jsonResponse(THRESHOLDS);
    if (path.endsWith('/corpus-sync/run')) return new Response(null, { status: 202 });
    if (path.endsWith('/corpus-sync') && method === 'PUT') {
      return jsonResponse({ ...SYNC, repository: (body as { repository: string }).repository });
    }
    if (path.endsWith('/corpus-sync')) return jsonResponse(SYNC);
    return jsonResponse({ detail: 'unexpected' }, 500);
  });
  return calls;
}

function renderAdmin() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Admin />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Admin', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('deactivates another account', async () => {
    // Arrange
    const calls = mockApi();
    renderAdmin();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Deactivate member@example.com' }));

    // Assert: US-03
    await waitFor(() =>
      expect(calls).toContainEqual({
        method: 'PATCH',
        path: '/api/admin/users/u2',
        body: { is_active: false },
      }),
    );
  });

  it('offers no way to deactivate your own account', async () => {
    // Arrange
    mockApi();

    // Act
    renderAdmin();

    // Assert
    const table = await screen.findByRole('table');
    const myRow = within(table).getByText('admin@example.com').closest('tr') as HTMLElement;
    expect(within(myRow).queryByRole('button')).not.toBeInTheDocument();
    expect(within(myRow).getByText('You')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
  });

  it('saves two thresholds between 0 and 1', async () => {
    // Arrange
    const calls = mockApi();
    renderAdmin();
    const user = userEvent.setup();
    const likely = await screen.findByLabelText('Likely duplicate at or above');

    // Act
    await user.clear(likely);
    await user.type(likely, '0.9');
    await user.clear(screen.getByLabelText('Possible duplicate at or above'));
    await user.type(screen.getByLabelText('Possible duplicate at or above'), '0.55');
    await user.click(screen.getByRole('button', { name: 'Save thresholds' }));

    // Assert: US-31 criterion 1
    expect(await screen.findByText(/New searches use these thresholds/)).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: 'PUT',
      path: '/api/admin/settings/duplicate-thresholds',
      body: { likely: 0.9, possible: 0.55 },
    });
  });

  it("shows the server's reason when thresholds are invalid", async () => {
    // Arrange
    mockApi({
      onThresholds: () =>
        jsonResponse(
          { detail: 'The possible threshold must be lower than the likely threshold.' },
          422,
        ),
    });
    renderAdmin();
    const user = userEvent.setup();
    const possible = await screen.findByLabelText('Possible duplicate at or above');

    // Act
    await user.clear(possible);
    await user.type(possible, '0.95');
    await user.click(screen.getByRole('button', { name: 'Save thresholds' }));

    // Assert: US-31 criterion 1, "with validation"
    expect(
      await screen.findByText('The possible threshold must be lower than the likely threshold.'),
    ).toBeInTheDocument();
  });

  it('refuses an empty threshold before sending anything', async () => {
    // Arrange
    const calls = mockApi();
    renderAdmin();
    const user = userEvent.setup();

    // Act
    await user.clear(await screen.findByLabelText('Likely duplicate at or above'));
    await user.click(screen.getByRole('button', { name: 'Save thresholds' }));

    // Assert
    expect(
      await screen.findByText('Enter both thresholds as numbers between 0 and 1.'),
    ).toBeInTheDocument();
    expect(calls).toEqual([]);
  });

  it('shows the import progress and starts an import on request', async () => {
    // Arrange
    const calls = mockApi();
    renderAdmin();
    const user = userEvent.setup();

    // Act
    expect(await screen.findByText('Paused by GitHub’s rate limit')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: /Import now/ }));

    // Assert: US-28
    expect(screen.getByText(/Nothing was lost/)).toBeInTheDocument();
    expect(screen.getByText('150 / 10')).toBeInTheDocument();
    await waitFor(() =>
      expect(calls).toContainEqual({
        method: 'POST',
        path: '/api/admin/corpus-sync/run',
        body: undefined,
      }),
    );
  });

  it('saves the repository to import from', async () => {
    // Arrange
    const calls = mockApi();
    renderAdmin();
    const user = userEvent.setup();
    const field = await screen.findByLabelText('Repository (owner/name)');
    await waitFor(() => expect(field).toHaveValue('acme/app'));

    // Act
    await user.clear(field);
    await user.type(field, 'nextcloud/server');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Assert
    await waitFor(() =>
      expect(calls).toContainEqual({
        method: 'PUT',
        path: '/api/admin/corpus-sync',
        body: { repository: 'nextcloud/server' },
      }),
    );
  });
});
