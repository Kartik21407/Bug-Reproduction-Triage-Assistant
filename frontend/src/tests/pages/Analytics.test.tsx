import { render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Analytics from '@/pages/Analytics';
import type { AnalyticsRead } from '@/types/api';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderAnalytics() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Analytics />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

const WITH_REPORTS: AnalyticsRead = {
  total_reports: 3,
  by_severity: [
    { name: 'Critical', count: 0 },
    { name: 'High', count: 2 },
    { name: 'Medium', count: 0 },
    { name: 'Low', count: 0 },
    { name: 'Not triaged', count: 1 },
  ],
  by_category: [
    { name: 'Authentication', count: 2 },
    { name: 'Not triaged', count: 1 },
  ],
  by_week: [
    { week_start: '2026-10-26', count: 1 },
    { week_start: '2026-11-02', count: 2 },
  ],
};

describe('Analytics', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the three charts with their numbers', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse(WITH_REPORTS));

    // Act
    renderAnalytics();

    // Assert: US-29 criterion 1
    expect(await screen.findByText('Based on your 3 reports.')).toBeInTheDocument();
    const severity = screen.getByRole('region', { name: 'Reports by severity' });
    const category = screen.getByRole('region', { name: 'Reports by category' });
    const weekly = screen.getByRole('region', { name: 'Reports per week' });
    expect(within(severity).getByRole('row', { name: 'High 2', hidden: true })).toBeInTheDocument();
    expect(
      within(category).getByRole('row', { name: 'Authentication 2', hidden: true }),
    ).toBeInTheDocument();
    expect(
      within(weekly).getByRole('row', { name: 'Week of 2 Nov 2', hidden: true }),
    ).toBeInTheDocument();
  });

  it('shows an empty state instead of charts when there are no reports', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ total_reports: 0, by_severity: [], by_category: [], by_week: [] }),
    );

    // Act
    renderAnalytics();

    // Assert: US-29 criterion 2
    expect(await screen.findByText(/You have no reports yet/)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Submit a report' })).toHaveAttribute(
      'href',
      '/reports/new',
    );
    expect(screen.queryByRole('region', { name: 'Reports by severity' })).not.toBeInTheDocument();
  });

  it("asks for the signed-in user's own numbers only", async () => {
    // Arrange
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => jsonResponse(WITH_REPORTS));

    // Act
    renderAnalytics();
    await screen.findByText('Based on your 3 reports.');

    // Assert: the server scopes /analytics to the session's user
    expect(fetchSpy.mock.calls.map(([url]) => String(url))).toEqual(['/api/analytics']);
  });
});
