import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import History from '@/pages/History';
import type { ReportRead } from '@/types/api';

function renderHistory() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <History />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function makeReport(overrides: Partial<ReportRead> = {}): ReportRead {
  return {
    id: '1',
    title: null,
    original_text: 'The login button does nothing when clicked twice.',
    logs: null,
    state: 'Draft',
    severity: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

describe('History', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the empty state explaining how to create the first report', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ items: [], total: 0 }),
    );

    // Act
    renderHistory();

    // Assert
    expect(await screen.findByText('No reports yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Submit a report' })).toHaveAttribute(
      'href',
      '/reports/new',
    );
  });

  it('lists reports with severity and status shown, even while unset', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ items: [makeReport()], total: 1 }),
    );

    // Act
    renderHistory();

    // Assert
    expect(await screen.findByText('Untitled report')).toBeInTheDocument();
    expect(screen.getByText('Not yet triaged · Draft')).toBeInTheDocument();
  });

  it('sends the search term to the API after the debounce delay', async () => {
    // Arrange
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => jsonResponse({ items: [], total: 0 }));
    renderHistory();
    const user = userEvent.setup();
    await screen.findByText('No reports yet');
    fetchSpy.mockClear();

    // Act
    await user.type(screen.getByLabelText('Search'), 'login');

    // Assert
    await waitFor(() => {
      const calledWithSearch = fetchSpy.mock.calls.some(([url]) =>
        String(url).includes('search=login'),
      );
      expect(calledWithSearch).toBe(true);
    });
  });

  it('sends the selected severity and status as filters', async () => {
    // Arrange
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => jsonResponse({ items: [], total: 0 }));
    renderHistory();
    const user = userEvent.setup();
    await screen.findByText('No reports yet');
    fetchSpy.mockClear();

    // Act
    await user.selectOptions(screen.getByLabelText('Severity'), 'Critical');
    await user.selectOptions(screen.getByLabelText('Status'), 'Draft');

    // Assert
    await waitFor(() => {
      const lastUrl = String(fetchSpy.mock.calls.at(-1)?.[0]);
      expect(lastUrl).toContain('severity=Critical');
      expect(lastUrl).toContain('state=Draft');
    });
  });

  it('shows a different empty message when filters produce no matches', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ items: [], total: 0 }),
    );
    renderHistory();
    const user = userEvent.setup();
    await screen.findByText('No reports yet');

    // Act
    await user.selectOptions(screen.getByLabelText('Severity'), 'Critical');

    // Assert
    expect(await screen.findByText('No reports match')).toBeInTheDocument();
  });
});
