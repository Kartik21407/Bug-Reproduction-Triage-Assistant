import { render, screen, within } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import Dashboard from '@/pages/Dashboard';
import type { MissingFieldsRead, ReportRead, ReportState } from '@/types/api';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function report(id: string, state: ReportState, title: string | null): ReportRead {
  return {
    id,
    title,
    original_text: `Original text of report ${id}, long enough.`,
    logs: null,
    state,
    severity: state === 'Draft' ? null : 'High',
    created_at: '2026-11-20T10:00:00Z',
    updated_at: '2026-11-20T10:00:00Z',
  };
}

const NO_MISSING: MissingFieldsRead = { analysed_reports: 0, fields: [] };

function mockApi(reports: ReportRead[], missing: MissingFieldsRead = NO_MISSING) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    const path = String(url);
    if (path.endsWith('/auth/me')) {
      return jsonResponse({
        id: 'u1',
        email: 'priya@example.com',
        is_admin: false,
        created_at: '2026-01-01T00:00:00Z',
      });
    }
    if (path.endsWith('/analytics/missing-fields')) return jsonResponse(missing);
    return jsonResponse({ items: reports, total: reports.length });
  });
}

function renderDashboard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Dashboard />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Dashboard', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('counts the reports by where they stand', async () => {
    // Arrange
    mockApi([
      report('r1', 'Draft', null),
      report('r2', 'Analysed', 'Login crash'),
      report('r3', 'Exported', 'Cart total wrong'),
      report('r4', 'Submitted', 'Search hangs'),
    ]);

    // Act
    renderDashboard();

    // Assert
    const stats = await screen.findByRole('region', { name: 'Your reports at a glance' });
    const value = (label: string) =>
      within(stats).getByText(label).parentElement?.querySelector('.text-3xl')?.textContent;
    expect(value('Total reports')).toBe('4');
    expect(value('Waiting for analysis')).toBe('1');
    expect(value('Ready to share')).toBe('2');
    expect(value('Filed on GitHub')).toBe('1');
  });

  it('lists the most recent reports as links with their status', async () => {
    // Arrange
    mockApi([report('r2', 'Analysed', 'Login crash'), report('r1', 'Draft', null)]);

    // Act
    renderDashboard();

    // Assert
    const link = await screen.findByRole('link', { name: /Login crash/ });
    expect(link).toHaveAttribute('href', '/reports/r2');
    expect(link).toHaveTextContent('Analysed');
    expect(screen.getByRole('link', { name: /Original text of report r1/ })).toHaveTextContent(
      'Not triaged',
    );
  });

  it('greets a new user with a way to submit their first report', async () => {
    // Arrange
    mockApi([]);

    // Act
    renderDashboard();

    // Assert
    expect(await screen.findByText('No reports yet')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Submit your first report/ })).toHaveAttribute(
      'href',
      '/reports/new',
    );
    expect(screen.getByRole('heading', { name: 'Welcome back, priya' })).toBeInTheDocument();
  });

  it('shows the fields most often missing, ranked, with counts', async () => {
    // Arrange
    mockApi([report('r2', 'Analysed', 'Login crash')], {
      analysed_reports: 4,
      fields: [
        { field: 'frequency', name: 'Frequency', count: 3 },
        { field: 'environment', name: 'Environment', count: 1 },
        { field: 'title', name: 'Title', count: 0 },
      ],
    });

    // Act
    renderDashboard();

    // Assert: US-30 criterion 1
    const list = await screen.findByRole('list', { name: 'Most commonly missing fields' });
    const items = within(list).getAllByRole('listitem');
    expect(items.map((item) => item.textContent)).toEqual([
      '1.Frequency3 of 4',
      '2.Environment1 of 4',
    ]);
  });
});
