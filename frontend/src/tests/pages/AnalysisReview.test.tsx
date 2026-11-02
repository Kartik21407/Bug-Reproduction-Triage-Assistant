import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import AnalysisReview from '@/pages/AnalysisReview';
import type { AnalysisRead, ExtractedField, ReportRead } from '@/types/api';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function missingField(): ExtractedField {
  return { value: null, source_quote: null, label: 'Missing', confidence: null, reason: null };
}

function makeReport(overrides: Partial<ReportRead> = {}): ReportRead {
  return {
    id: 'report-1',
    title: null,
    original_text: 'Login crashes when I click submit after entering a wrong password.',
    logs: null,
    state: 'Draft',
    severity: null,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeAnalysis(overrides: Partial<AnalysisRead> = {}): AnalysisRead {
  return {
    extraction: {
      title: missingField(),
      summary: missingField(),
      expected_behaviour: missingField(),
      actual_behaviour: missingField(),
      frequency: missingField(),
      steps: [],
      environment: [],
      error_messages: [],
    },
    questions: [],
    completeness: {
      verified_count: 0,
      total: 5,
      missing_fields: [],
      needs_confirmation_fields: [],
    },
    steps_flagged_for_review: false,
    ...overrides,
  };
}

function renderAnalysisReview(id = 'report-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/reports/${id}/analysis`]}>
        <Routes>
          <Route path="/reports/:id/analysis" element={<AnalysisReview />} />
          <Route path="/reports/:id/mask" element={<div>Masking review page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function mockFetchFor(report: ReportRead, analysis: AnalysisRead) {
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url) => {
    if (String(url).endsWith('/analysis')) return jsonResponse(analysis);
    return jsonResponse(report);
  });
}

describe('AnalysisReview', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('points to masking review when the report has never been analysed', async () => {
    // Arrange
    mockFetchFor(makeReport(), makeAnalysis());

    // Act
    renderAnalysisReview();

    // Assert
    expect(await screen.findByText('This report has not been analysed yet.')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Review and analyse' })).toHaveAttribute(
      'href',
      '/reports/report-1/mask',
    );
  });

  it('shows extracted fields with their labels', async () => {
    // Arrange
    const analysis = makeAnalysis({
      extraction: {
        ...makeAnalysis().extraction,
        expected_behaviour: {
          value: 'An error message is shown',
          source_quote: 'wrong password',
          label: 'Explicit',
          confidence: 0.9,
          reason: 'Stated directly',
        },
      },
      completeness: {
        verified_count: 1,
        total: 5,
        missing_fields: [],
        needs_confirmation_fields: [],
      },
    });
    mockFetchFor(makeReport({ state: 'Analysed', title: 'Login crash' }), analysis);

    // Act
    renderAnalysisReview();

    // Assert
    expect(await screen.findByText('An error message is shown')).toBeInTheDocument();
    expect(screen.getByText('Explicit')).toBeInTheDocument();
    expect(screen.getByText('Completeness: 1/5 essential fields verified')).toBeInTheDocument();
  });

  it('shows a review warning when more than seven steps were extracted', async () => {
    // Arrange
    const analysis = makeAnalysis({
      extraction: {
        ...makeAnalysis().extraction,
        steps: Array.from({ length: 10 }, (_, i) => ({
          value: `Do thing number ${i}`,
          source_quote: 'x',
          label: 'Explicit' as const,
          confidence: 0.9,
          reason: 'x',
        })),
      },
      steps_flagged_for_review: true,
    });
    mockFetchFor(makeReport({ state: 'Analysed' }), analysis);

    // Act
    renderAnalysisReview();

    // Assert
    expect(
      await screen.findByText(
        'More than seven steps were extracted. Review the full list before filing; nothing has been shortened.',
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText(/^Step \d+$/)).toHaveLength(10);
  });

  it('highlights the source text when View source is clicked', async () => {
    // Arrange
    const analysis = makeAnalysis({
      extraction: {
        ...makeAnalysis().extraction,
        actual_behaviour: {
          value: 'the app crashes',
          source_quote: 'crashes when I click submit',
          label: 'Explicit',
          confidence: 0.9,
          reason: 'Stated directly',
        },
      },
    });
    mockFetchFor(makeReport({ state: 'Analysed' }), analysis);
    renderAnalysisReview();
    const user = userEvent.setup();
    await screen.findByText('the app crashes');

    // Act
    await user.click(screen.getByRole('button', { name: 'View source text' }));

    // Assert
    expect(screen.getByText('crashes when I click submit')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Clear highlight' })).toBeInTheDocument();
  });

  it('answers a follow-up question', async () => {
    // Arrange
    let answerBody: unknown;
    const analysis = makeAnalysis({
      questions: [
        {
          id: 'q1',
          field: 'frequency',
          question: 'How often does this happen?',
          reason: 'Not stated',
          model_proposed: false,
          answer: null,
          answered_at: null,
        },
      ],
    });
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      if (init?.method === 'POST' && String(url).includes('/answer')) {
        answerBody = JSON.parse(init.body as string);
        return jsonResponse(makeAnalysis());
      }
      if (String(url).endsWith('/analysis')) return jsonResponse(analysis);
      return jsonResponse(makeReport({ state: 'Analysed' }));
    });
    renderAnalysisReview();
    const user = userEvent.setup();
    await screen.findByText('How often does this happen?');

    // Act
    await user.type(screen.getByLabelText('Answer: How often does this happen?'), 'Every time');
    await user.click(screen.getByRole('button', { name: 'Answer' }));

    // Assert
    expect(answerBody).toEqual({ answer: 'Every time' });
  });

  it('shows an already-answered question as answered, not as a form', async () => {
    // Arrange
    const analysis = makeAnalysis({
      questions: [
        {
          id: 'q1',
          field: 'frequency',
          question: 'How often does this happen?',
          reason: 'Not stated',
          model_proposed: false,
          answer: 'Every time',
          answered_at: '2026-01-02T00:00:00Z',
        },
      ],
    });
    mockFetchFor(makeReport({ state: 'Analysed' }), analysis);

    // Act
    renderAnalysisReview();

    // Assert
    expect(await screen.findByText('Answered: Every time')).toBeInTheDocument();
  });

  it('corrects an environment detail', async () => {
    // Arrange
    let correctBody: unknown;
    const analysis = makeAnalysis({
      extraction: {
        ...makeAnalysis().extraction,
        environment: [
          { name: 'browser', value: 'Chrome', source_quote: 'chrome', label: 'Explicit' },
        ],
      },
    });
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      if (init?.method === 'POST' && String(url).endsWith('/environment')) {
        correctBody = JSON.parse(init.body as string);
        return jsonResponse(analysis);
      }
      if (String(url).endsWith('/analysis')) return jsonResponse(analysis);
      return jsonResponse(makeReport({ state: 'Analysed' }));
    });
    renderAnalysisReview();
    const user = userEvent.setup();
    await screen.findByText('browser');

    // Act
    await user.click(screen.getByRole('button', { name: 'Correct' }));
    const input = screen.getByLabelText('Value for browser');
    await user.clear(input);
    await user.type(input, 'Firefox');
    await user.click(screen.getByRole('button', { name: 'Save' }));

    // Assert
    expect(correctBody).toEqual({ corrections: [{ name: 'browser', value: 'Firefox' }] });
  });

  it('shows a not-found message for a 404', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ detail: 'Report not found' }, 404),
    );

    // Act
    renderAnalysisReview();

    // Assert
    expect(await screen.findByText('Report not found.')).toBeInTheDocument();
  });
});
