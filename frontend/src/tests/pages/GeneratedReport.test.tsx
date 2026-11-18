import { render, screen } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GeneratedReport from '@/pages/GeneratedReport';
import type { GeneratedReport as GeneratedReportData, ReportLine, ReportRead } from '@/types/api';

const HEADINGS = [
  'Title',
  'Summary',
  'Steps to Reproduce',
  'Expected',
  'Actual',
  'Environment',
  'Error Details',
  'Severity',
  'Priority',
  'Category',
  'Reproducibility',
  'Possible Duplicates',
  'Additional Information',
];

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function makeReport(overrides: Partial<ReportRead> = {}): ReportRead {
  return {
    id: 'report-1',
    title: 'Login crash',
    original_text: 'Login crashes when I enter a wrong password.',
    logs: null,
    state: 'Analysed',
    severity: 'High',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function line(text: string, overrides: Partial<ReportLine> = {}): ReportLine {
  return { text, label: null, note: null, url: null, preformatted: false, ...overrides };
}

function notProvidedReport(): GeneratedReportData {
  return {
    sections: HEADINGS.map((heading) => ({
      key: heading.toLowerCase(),
      heading,
      provided: false,
      lines: [line('Not provided')],
    })),
  };
}

function withSection(
  report: GeneratedReportData,
  heading: string,
  lines: ReportLine[],
): GeneratedReportData {
  return {
    sections: report.sections.map((section) =>
      section.heading === heading ? { ...section, provided: true, lines } : section,
    ),
  };
}

function mockFetch(report: ReportRead, generated: GeneratedReportData) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (String(url).endsWith('/report')) return jsonResponse(generated);
    return jsonResponse(report);
  });
}

function renderGeneratedReport(id = 'report-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/reports/${id}/report`]}>
        <Routes>
          <Route path="/reports/:id/report" element={<GeneratedReport />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GeneratedReport', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows every section of the template in order', async () => {
    // Arrange
    mockFetch(makeReport(), notProvidedReport());

    // Act
    renderGeneratedReport();

    // Assert: US-23 criterion 1
    await screen.findByText('Title');
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(HEADINGS);
  });

  it('shows "Not provided" for every missing value', async () => {
    // Arrange
    mockFetch(makeReport(), notProvidedReport());

    // Act
    renderGeneratedReport();

    // Assert: US-23 criterion 2
    expect(await screen.findAllByText('Not provided')).toHaveLength(HEADINGS.length);
  });

  it('shows duplicate candidates as links', async () => {
    // Arrange
    const generated = withSection(notProvidedReport(), 'Possible Duplicates', [
      line('Login page crashes after a wrong password', {
        url: 'https://github.com/acme/app/issues/7',
        note: 'Likely duplicate, similarity 0.91',
      }),
    ]);
    mockFetch(makeReport(), generated);

    // Act
    renderGeneratedReport();

    // Assert: US-23 criterion 3
    expect(
      await screen.findByRole('link', { name: 'Login page crashes after a wrong password' }),
    ).toHaveAttribute('href', 'https://github.com/acme/app/issues/7');
    expect(screen.getByText('Likely duplicate, similarity 0.91')).toBeInTheDocument();
  });

  it('marks a value that is not confirmed with its label', async () => {
    // Arrange
    const generated = withSection(
      withSection(notProvidedReport(), 'Title', [line('Login crash', { label: 'Explicit' })]),
      'Summary',
      [line('Login closes instead of showing an error', { label: 'Inferred' })],
    );
    mockFetch(makeReport(), generated);

    // Act
    renderGeneratedReport();

    // Assert
    expect(await screen.findByText('Login closes instead of showing an error')).toBeInTheDocument();
    expect(screen.getByText('Inferred')).toBeInTheDocument();
    expect(screen.queryByText('Explicit')).not.toBeInTheDocument();
  });

  it('asks for analysis first for a Draft report', async () => {
    // Arrange
    mockFetch(makeReport({ state: 'Draft', severity: null }), notProvidedReport());

    // Act
    renderGeneratedReport();

    // Assert
    expect(await screen.findByText(/has not been analysed yet/)).toBeInTheDocument();
  });
});
