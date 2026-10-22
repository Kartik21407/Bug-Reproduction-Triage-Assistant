import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import ReportDetail from '@/pages/ReportDetail';
import type { ReportRead } from '@/types/api';

function makeReport(overrides: Partial<ReportRead> = {}): ReportRead {
  return {
    id: 'report-1',
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

function renderReportDetail(id = 'report-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/reports/${id}`]}>
        <Routes>
          <Route path="/reports/:id" element={<ReportDetail />} />
          <Route path="/reports" element={<div>History page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ReportDetail', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the report text and a placeholder for unset severity and title', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse(makeReport()));

    // Act
    renderReportDetail();

    // Assert
    expect(await screen.findByText('Untitled report')).toBeInTheDocument();
    expect(
      screen.getByText('The login button does nothing when clicked twice.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Not yet triaged · Draft', { exact: false })).toBeInTheDocument();
  });

  it('shows a not-found message for a 404, without revealing whether the id exists', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ detail: 'Report not found' }, 404),
    );

    // Act
    renderReportDetail();

    // Assert
    expect(await screen.findByText('Report not found.')).toBeInTheDocument();
  });

  it('switches to an editable form pre-filled with the current text', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () => jsonResponse(makeReport()));
    renderReportDetail();
    const user = userEvent.setup();
    await screen.findByText('Untitled report');

    // Act
    await user.click(screen.getByRole('button', { name: 'Edit' }));

    // Assert
    expect(screen.getByLabelText('Bug description')).toHaveValue(
      'The login button does nothing when clicked twice.',
    );
  });

  it('saves an edit and returns to view mode', async () => {
    // Arrange
    const updated = makeReport({ original_text: 'An edited description of the bug.' });
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
      if (init?.method === 'PATCH') return jsonResponse(updated);
      return jsonResponse(makeReport());
    });
    renderReportDetail();
    const user = userEvent.setup();
    await screen.findByText('Untitled report');
    await user.click(screen.getByRole('button', { name: 'Edit' }));

    // Act
    const textbox = screen.getByLabelText('Bug description');
    await user.clear(textbox);
    await user.type(textbox, 'An edited description of the bug.');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Assert
    expect(await screen.findByText('An edited description of the bug.')).toBeInTheDocument();
  });

  it('deletes the report after confirmation and navigates to history', async () => {
    // Arrange
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
      if (init?.method === 'DELETE') return new Response(null, { status: 204 });
      return jsonResponse(makeReport());
    });
    renderReportDetail();
    const user = userEvent.setup();
    await screen.findByText('Untitled report');

    // Act
    await user.click(screen.getByRole('button', { name: 'Delete' }));

    // Assert
    expect(window.confirm).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByText('History page')).toBeInTheDocument());
  });

  it('does not delete when the user cancels the confirmation', async () => {
    // Arrange
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const fetchSpy = vi
      .spyOn(globalThis, 'fetch')
      .mockImplementation(async () => jsonResponse(makeReport()));
    renderReportDetail();
    const user = userEvent.setup();
    await screen.findByText('Untitled report');
    fetchSpy.mockClear();

    // Act
    await user.click(screen.getByRole('button', { name: 'Delete' }));

    // Assert
    expect(window.confirm).toHaveBeenCalled();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
});
