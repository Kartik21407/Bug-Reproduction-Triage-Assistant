import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import TriageReview from '@/pages/TriageReview';
import type { DuplicatesRead, ReportRead, TriageRead, TriageValue } from '@/types/api';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function makeReport(overrides: Partial<ReportRead> = {}): ReportRead {
  return {
    id: 'report-1',
    title: 'Login crashes on a wrong password',
    original_text: 'Login crashes sometimes when I enter a wrong password.',
    logs: null,
    state: 'Analysed',
    severity: 'High',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function value(v: string, reason: string, options: string[], overridden = false): TriageValue {
  return { value: v, suggested_value: overridden ? 'High' : v, reason, overridden, options };
}

function makeTriage(overrides: Partial<TriageRead> = {}): TriageRead {
  return {
    severity: value('High', 'Mentions "crashes", so High', ['Critical', 'High', 'Medium', 'Low']),
    priority: value('P2', 'Follows severity High, so P2', ['P1', 'P2', 'P3', 'P4']),
    category: value('Authentication', 'Mentions "login", so Authentication', [
      'UI',
      'Authentication',
      'Performance',
      'Database',
      'API',
      'Functional',
      'Security',
      'Compatibility',
    ]),
    reproducibility: value('Sometimes', 'Mentions "sometimes", so Sometimes', [
      'Always',
      'Sometimes',
      'Rarely',
      'Unable to reproduce',
      'Unknown',
    ]),
    ...overrides,
  };
}

const NOT_SEARCHED: DuplicatesRead = { searched: false, compared_count: 0, candidates: [] };

const SEARCHED: DuplicatesRead = {
  searched: true,
  compared_count: 300,
  candidates: [
    {
      id: 'c1',
      candidate_id: 'cand-1',
      source: 'corpus',
      title: 'Login page crashes after a wrong password',
      url: 'https://github.com/acme/app/issues/7',
      score: 0.91,
      label: 'Likely duplicate',
      rank: 1,
      decision: null,
      explanation: null,
    },
    {
      id: 'r2',
      candidate_id: 'cand-2',
      source: 'report',
      title: 'Sign in closes the app',
      url: '/reports/r2',
      score: 0.66,
      label: 'Possible duplicate',
      rank: 2,
      decision: null,
      explanation: null,
    },
  ],
};

interface MockResponses {
  report?: ReportRead;
  triage?: TriageRead;
  duplicates?: DuplicatesRead;
  onPatch?: (body: unknown) => TriageRead;
  onSearch?: () => DuplicatesRead;
  onDecide?: (path: string, body: unknown) => DuplicatesRead;
}

function mockFetch({ report, triage, duplicates, onPatch, onSearch, onDecide }: MockResponses) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    const path = String(url);
    if (path.endsWith('/decision') && init?.method === 'PUT') {
      return jsonResponse(onDecide?.(path, JSON.parse(init.body as string)) ?? SEARCHED);
    }
    if (path.endsWith('/triage') && init?.method === 'PATCH') {
      return jsonResponse(onPatch?.(JSON.parse(init.body as string)) ?? makeTriage());
    }
    if (path.endsWith('/triage/history')) return jsonResponse([]);
    if (path.endsWith('/triage')) return jsonResponse(triage ?? makeTriage());
    if (path.endsWith('/duplicates') && init?.method === 'POST') {
      return jsonResponse(onSearch?.() ?? SEARCHED);
    }
    if (path.endsWith('/duplicates')) return jsonResponse(duplicates ?? NOT_SEARCHED);
    return jsonResponse(report ?? makeReport());
  });
}

function renderTriageReview(id = 'report-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/reports/${id}/triage`]}>
        <Routes>
          <Route path="/reports/:id/triage" element={<TriageReview />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('TriageReview', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('asks for analysis first and does not request triage for a Draft report', async () => {
    // Arrange
    const fetchSpy = mockFetch({ report: makeReport({ state: 'Draft', severity: null }) });

    // Act
    renderTriageReview();

    // Assert
    expect(await screen.findByText(/has not been analysed yet/)).toBeInTheDocument();
    expect(fetchSpy.mock.calls.some(([url]) => String(url).endsWith('/triage'))).toBe(false);
  });

  it('shows each suggestion in an editable dropdown with its reason', async () => {
    // Arrange
    mockFetch({});

    // Act
    renderTriageReview();

    // Assert: US-15 criteria 2 and 3
    const severity = await screen.findByLabelText('Severity');
    expect(severity).toHaveValue('High');
    expect(screen.getByText('Why: Mentions "crashes", so High')).toBeInTheDocument();
    expect(screen.getByLabelText('Category')).toHaveValue('Authentication');
    expect(screen.getByLabelText('Reproducibility')).toHaveValue('Sometimes');
  });

  it('labels priority as a suggestion for the project manager to decide', async () => {
    // Arrange
    mockFetch({});

    // Act
    renderTriageReview();

    // Assert: US-16 criteria 1 and 2
    expect(await screen.findByLabelText('Priority')).toHaveValue('P2');
    expect(
      screen.getByText('A suggestion only. The project manager decides priority.'),
    ).toBeInTheDocument();
  });

  it('saves an override and marks it as changed', async () => {
    // Arrange
    let patchBody: unknown;
    mockFetch({
      onPatch: (body) => {
        patchBody = body;
        return makeTriage({
          severity: value(
            'Low',
            'Mentions "crashes", so High',
            ['Critical', 'High', 'Medium', 'Low'],
            true,
          ),
        });
      },
    });
    renderTriageReview();
    const user = userEvent.setup();
    const severity = await screen.findByLabelText('Severity');

    // Act
    await user.selectOptions(severity, 'Low');

    // Assert: US-15 criterion 4
    expect(patchBody).toEqual({ field: 'severity', value: 'Low' });
    expect(await screen.findByText('Changed by you')).toBeInTheDocument();
    expect(screen.getByText('Suggested High: Mentions "crashes", so High')).toBeInTheDocument();
  });

  it('runs a search and lists candidates most similar first with their labels', async () => {
    // Arrange
    let searched = false;
    mockFetch({
      onSearch: () => {
        searched = true;
        return SEARCHED;
      },
    });
    renderTriageReview();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Find similar issues' }));

    // Assert: US-20 criteria 1 and 2
    expect(searched).toBe(true);
    const list = await screen.findByRole('list', { name: 'Similar existing issues' });
    const items = within(list).getAllByRole('listitem');
    expect(items[0]).toHaveTextContent('Login page crashes after a wrong password');
    expect(items[0]).toHaveTextContent('Likely duplicate');
    expect(items[0]).toHaveTextContent('Similarity 0.91');
    expect(items[1]).toHaveTextContent('Possible duplicate');
    expect(
      screen.getByRole('link', { name: 'Login page crashes after a wrong password' }),
    ).toHaveAttribute('href', 'https://github.com/acme/app/issues/7');
    expect(screen.getByRole('link', { name: 'Sign in closes the app' })).toHaveAttribute(
      'href',
      '/reports/r2',
    );
  });

  it('never says that a report is a duplicate', async () => {
    // Arrange
    mockFetch({ duplicates: SEARCHED });

    // Act
    renderTriageReview();
    await screen.findByText('Login page crashes after a wrong password');

    // Assert: US-20 criterion 3
    expect(document.body.textContent?.toLowerCase()).not.toContain('is a duplicate');
  });

  it('says plainly when nothing similar was found', async () => {
    // Arrange
    mockFetch({ duplicates: { searched: true, compared_count: 120, candidates: [] } });

    // Act
    renderTriageReview();

    // Assert
    expect(
      await screen.findByText('No similar issues found among the 120 compared.'),
    ).toBeInTheDocument();
  });

  it("shows the server's message when the search is unavailable", async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
      const path = String(url);
      if (path.endsWith('/duplicates') && init?.method === 'POST') {
        return jsonResponse(
          { detail: 'Duplicate search is unavailable right now. Try again later.' },
          503,
        );
      }
      if (path.endsWith('/triage/history')) return jsonResponse([]);
      if (path.endsWith('/triage')) return jsonResponse(makeTriage());
      if (path.endsWith('/duplicates')) return jsonResponse(NOT_SEARCHED);
      return jsonResponse(makeReport());
    });
    renderTriageReview();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Find similar issues' }));

    // Assert
    expect(
      await screen.findByText('Duplicate search is unavailable right now. Try again later.'),
    ).toBeInTheDocument();
  });

  it('records a person confirming a candidate as a duplicate', async () => {
    // Arrange
    const calls: { path: string; body: unknown }[] = [];
    mockFetch({
      duplicates: SEARCHED,
      onDecide: (path, body) => {
        calls.push({ path, body });
        return {
          ...SEARCHED,
          candidates: SEARCHED.candidates.map((candidate) =>
            candidate.candidate_id === 'cand-1'
              ? { ...candidate, decision: 'duplicate' }
              : candidate,
          ),
        };
      },
    });
    renderTriageReview();
    const user = userEvent.setup();
    const button = await screen.findByRole('button', {
      name: 'Duplicate: Login page crashes after a wrong password',
    });

    // Act
    await user.click(button);

    // Assert: US-21 criterion 1
    expect(calls).toEqual([
      { path: '/api/reports/report-1/duplicates/cand-1/decision', body: { decision: 'duplicate' } },
    ]);
    expect(
      await screen.findByRole('button', {
        name: 'Duplicate: Login page crashes after a wrong password',
        pressed: true,
      }),
    ).toBeInTheDocument();
  });

  it('takes a decision back when the chosen button is clicked again', async () => {
    // Arrange
    const decided: DuplicatesRead = {
      ...SEARCHED,
      candidates: SEARCHED.candidates.map((candidate) =>
        candidate.candidate_id === 'cand-2'
          ? { ...candidate, decision: 'not_duplicate' }
          : candidate,
      ),
    };
    const bodies: unknown[] = [];
    mockFetch({
      duplicates: decided,
      onDecide: (_path, body) => {
        bodies.push(body);
        return SEARCHED;
      },
    });
    renderTriageReview();
    const user = userEvent.setup();

    // Act
    await user.click(
      await screen.findByRole('button', { name: 'Not duplicate: Sign in closes the app' }),
    );

    // Assert
    expect(bodies).toEqual([{ decision: null }]);
  });

  it('shows a not-found message for a 404', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ detail: 'Report not found' }, 404),
    );

    // Act
    renderTriageReview();

    // Assert
    expect(await screen.findByText('Report not found.')).toBeInTheDocument();
  });
});
