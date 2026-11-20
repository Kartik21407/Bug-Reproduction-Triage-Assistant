import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GeneratedReport from '@/pages/GeneratedReport';
import type {
  EditableValues,
  GeneratedReport as GeneratedReportData,
  MarkdownRead,
  ReportLine,
  ReportRead,
  ReportSection,
} from '@/types/api';

const SECTIONS: { key: string; heading: string; fields: string[] }[] = [
  { key: 'title', heading: 'Title', fields: ['title'] },
  { key: 'summary', heading: 'Summary', fields: ['summary'] },
  { key: 'steps', heading: 'Steps to Reproduce', fields: ['steps'] },
  { key: 'expected', heading: 'Expected', fields: ['expected_behaviour'] },
  { key: 'actual', heading: 'Actual', fields: ['actual_behaviour'] },
  { key: 'environment', heading: 'Environment', fields: ['environment'] },
  { key: 'error_details', heading: 'Error Details', fields: ['error_messages'] },
  { key: 'severity', heading: 'Severity', fields: ['severity'] },
  { key: 'priority', heading: 'Priority', fields: ['priority'] },
  { key: 'category', heading: 'Category', fields: ['category'] },
  { key: 'reproducibility', heading: 'Reproducibility', fields: ['reproducibility'] },
  { key: 'duplicates', heading: 'Possible Duplicates', fields: [] },
  {
    key: 'additional',
    heading: 'Additional Information',
    fields: ['frequency', 'additional_information'],
  },
];

const HEADINGS = SECTIONS.map((section) => section.heading);

const EMPTY_VALUES: EditableValues = {
  title: null,
  summary: null,
  expected_behaviour: null,
  actual_behaviour: null,
  frequency: null,
  additional_information: null,
  steps: [],
  error_messages: [],
  environment: [],
};

const NO_WARNINGS: MarkdownRead = { markdown: '## Title\n\n*Not provided*\n', warnings: [] };

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
    sections: SECTIONS.map((section): ReportSection => ({
      ...section,
      provided: false,
      edited: false,
      lines: [line('Not provided')],
    })),
    values: EMPTY_VALUES,
  };
}

function withSection(
  report: GeneratedReportData,
  heading: string,
  lines: ReportLine[],
  edited = false,
): GeneratedReportData {
  return {
    ...report,
    sections: report.sections.map((section) =>
      section.heading === heading ? { ...section, provided: true, lines, edited } : section,
    ),
  };
}

interface Call {
  method: string;
  path: string;
  body: unknown;
}

interface MockOptions {
  report?: ReportRead;
  generated?: GeneratedReportData;
  markdown?: MarkdownRead;
  afterChange?: GeneratedReportData;
}

function mockFetch({ report, generated, markdown, afterChange }: MockOptions = {}) {
  const calls: Call[] = [];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    const path = String(url);
    const method = init?.method ?? 'GET';
    const body = init?.body ? JSON.parse(init.body as string) : undefined;
    if (method !== 'GET') calls.push({ method, path, body });
    if (method === 'PATCH' || method === 'DELETE') {
      return jsonResponse(afterChange ?? generated ?? notProvidedReport());
    }
    if (path.endsWith('/export') || path.endsWith('/review')) {
      return jsonResponse(
        makeReport({ ...report, state: path.endsWith('/export') ? 'Exported' : 'Reviewed' }),
      );
    }
    if (path.endsWith('/report')) return jsonResponse(generated ?? notProvidedReport());
    if (path.endsWith('/markdown')) return jsonResponse(markdown ?? NO_WARNINGS);
    if (path.endsWith('/triage')) return jsonResponse({ detail: 'Not triaged' }, 404);
    return jsonResponse(report ?? makeReport());
  });
  return calls;
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
    mockFetch();

    // Act
    renderGeneratedReport();

    // Assert: US-23 criterion 1
    await screen.findByText('Title');
    const headings = screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(HEADINGS);
  });

  it('shows "Not provided" for every missing value', async () => {
    // Arrange
    mockFetch();

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
    mockFetch({ generated });

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
    mockFetch({ generated });

    // Act
    renderGeneratedReport();

    // Assert
    expect(await screen.findByText('Login closes instead of showing an error')).toBeInTheDocument();
    expect(screen.getByText('Inferred')).toBeInTheDocument();
    expect(screen.queryByText('Explicit')).not.toBeInTheDocument();
  });

  it('asks for analysis first for a Draft report', async () => {
    // Arrange
    mockFetch({ report: makeReport({ state: 'Draft', severity: null }) });

    // Act
    renderGeneratedReport();

    // Assert
    expect(await screen.findByText(/has not been analysed yet/)).toBeInTheDocument();
  });

  it.skip('offers an edit button on every section a person can change', async () => {
    // Arrange
    mockFetch();

    // Act
    renderGeneratedReport();
    await screen.findByText('Title');

    // Assert: US-24 criterion 1 (duplicates are decided on the triage page)
    const editable = SECTIONS.filter((section) => section.fields.length > 0);
    for (const section of editable) {
      expect(screen.getByRole('button', { name: `Edit ${section.heading}` })).toBeInTheDocument();
    }
    expect(
      screen.queryByRole('button', { name: 'Edit Possible Duplicates' }),
    ).not.toBeInTheDocument();
  });

  it.skip('saves an edited section and shows the new value', async () => {
    // Arrange
    const afterChange = withSection(
      notProvidedReport(),
      'Summary',
      [line('Login closes on a wrong password')],
      true,
    );
    const calls = mockFetch({ afterChange });
    renderGeneratedReport();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Edit Summary' }));
    await user.type(screen.getByLabelText('Summary'), 'Login closes on a wrong password');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Assert: US-24 criterion 2
    expect(await screen.findByText('Login closes on a wrong password')).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: 'PATCH',
      path: '/api/reports/report-1/report',
      body: { field: 'summary', text: 'Login closes on a wrong password' },
    });
  });

  it.skip('sends each step as its own item', async () => {
    // Arrange
    const calls = mockFetch();
    renderGeneratedReport();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Edit Steps to Reproduce' }));
    await user.type(
      screen.getByLabelText('Steps to Reproduce, one per line'),
      'Open login{Enter}Enter a wrong password',
    );
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Assert
    await waitFor(() =>
      expect(calls).toContainEqual({
        method: 'PATCH',
        path: '/api/reports/report-1/report',
        body: { field: 'steps', items: ['Open login', 'Enter a wrong password'] },
      }),
    );
  });

  it.skip('asks for name: value lines in the environment editor', async () => {
    // Arrange
    const calls = mockFetch();
    renderGeneratedReport();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Edit Environment' }));
    await user.type(
      screen.getByLabelText('Environment, one detail per line as name: value'),
      'Chrome',
    );
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Assert
    expect(await screen.findByText(/Write each detail on its own line/)).toBeInTheDocument();
    expect(calls).toEqual([]);
  });

  it.skip('resets an edited section to the suggestion', async () => {
    // Arrange
    const generated = withSection(notProvidedReport(), 'Summary', [line('My own words')], true);
    const calls = mockFetch({ generated, afterChange: notProvidedReport() });
    renderGeneratedReport();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Reset Summary to suggested' }));

    // Assert: US-24 criterion 3
    await waitFor(() => expect(screen.queryByText('My own words')).not.toBeInTheDocument());
    expect(calls).toContainEqual({
      method: 'DELETE',
      path: '/api/reports/report-1/report/fields/summary',
      body: undefined,
    });
  });

  it.skip('only offers a reset on a section that was edited', async () => {
    // Arrange
    mockFetch();

    // Act
    renderGeneratedReport();
    await screen.findByText('Title');

    // Assert
    expect(screen.queryByRole('button', { name: /to suggested$/ })).not.toBeInTheDocument();
  });

  it.skip('copies the Markdown with one click and records the export', async () => {
    // Arrange
    const writeText = vi.fn().mockResolvedValue(undefined);
    const markdown = { markdown: '## Title\n\nLogin crash\n', warnings: [] };
    const calls = mockFetch({ markdown });
    renderGeneratedReport();
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const button = await screen.findByRole('button', { name: 'Copy as Markdown' });
    await waitFor(() => expect(button).toBeEnabled());

    // Act
    await user.click(button);

    // Assert: US-25 criterion 1
    expect(writeText).toHaveBeenCalledWith('## Title\n\nLogin crash\n');
    expect(await screen.findByRole('button', { name: 'Copied' })).toBeInTheDocument();
    await waitFor(() =>
      expect(calls).toContainEqual({
        method: 'POST',
        path: '/api/reports/report-1/export',
        body: undefined,
      }),
    );
  });

  it.skip('shows the text to copy by hand when the browser blocks copying', async () => {
    // Arrange
    const writeText = vi.fn().mockRejectedValue(new Error('blocked'));
    mockFetch({ markdown: { markdown: '## Title\n\nLogin crash\n', warnings: [] } });
    renderGeneratedReport();
    const user = userEvent.setup();
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    const button = await screen.findByRole('button', { name: 'Copy as Markdown' });
    await waitFor(() => expect(button).toBeEnabled());

    // Act
    await user.click(button);

    // Assert
    expect(await screen.findByLabelText(/Copying was blocked by the browser/)).toHaveValue(
      '## Title\n\nLogin crash\n',
    );
  });

  it.skip('warns about what is still missing before sharing', async () => {
    // Arrange
    mockFetch({
      markdown: {
        markdown: '## Title\n',
        warnings: ['Still missing: expected behaviour, frequency'],
      },
    });

    // Act
    renderGeneratedReport();

    // Assert
    expect(await screen.findByText('Before you share this report')).toBeInTheDocument();
    expect(screen.getByText('Still missing: expected behaviour, frequency')).toBeInTheDocument();
  });

  it.skip('marks an analysed report as reviewed', async () => {
    // Arrange
    const calls = mockFetch();
    renderGeneratedReport();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Mark as reviewed' }));

    // Assert
    expect(await screen.findByText('Status: Reviewed')).toBeInTheDocument();
    expect(calls).toContainEqual({
      method: 'POST',
      path: '/api/reports/report-1/review',
      body: undefined,
    });
  });

  it.skip('links on to filing the report on GitHub', async () => {
    // Arrange
    mockFetch();

    // Act
    renderGeneratedReport();

    // Assert
    expect(await screen.findByRole('link', { name: 'File on GitHub' })).toHaveAttribute(
      'href',
      '/reports/report-1/github',
    );
  });
});

