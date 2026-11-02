import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import MaskingReview from '@/pages/MaskingReview';

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function renderMaskingReview(id = 'report-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/reports/${id}/mask`]}>
        <Routes>
          <Route path="/reports/:id/mask" element={<MaskingReview />} />
          <Route path="/reports/:id/analysis" element={<div>Analysis page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('MaskingReview', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the detected items by type', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({
        masked_text: 'Contact me at [masked]',
        items: [{ type: 'email', original_text: 'a@b.com', start: 14, end: 21 }],
      }),
    );

    // Act
    renderMaskingReview();

    // Assert
    expect(await screen.findByText('Email')).toBeInTheDocument();
    expect(screen.getByText('a@b.com')).toBeInTheDocument();
  });

  it('shows a review is still available when nothing was detected', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({ masked_text: 'Nothing secret here', items: [] }),
    );

    // Act
    renderMaskingReview();

    // Assert
    expect(
      await screen.findByText(
        'Nothing was detected automatically. You can still mask something by hand below.',
      ),
    ).toBeInTheDocument();
  });

  it('marks a detected item as not a secret', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockImplementation(async () =>
      jsonResponse({
        masked_text: 'Contact me at [masked]',
        items: [{ type: 'email', original_text: 'a@b.com', start: 14, end: 21 }],
      }),
    );
    renderMaskingReview();
    const user = userEvent.setup();
    await screen.findByText('Email');

    // Act
    await user.click(screen.getByRole('button', { name: 'Not a secret' }));

    // Assert
    expect(screen.getByRole('button', { name: 'Mask again' })).toBeInTheDocument();
  });

  it('adds and runs analysis with a manually masked value', async () => {
    // Arrange
    let analyzeBody: unknown;
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (_url, init) => {
      if (init?.method === 'POST' && String(_url).endsWith('/analyze')) {
        analyzeBody = JSON.parse(init.body as string);
        return jsonResponse({
          masked_items: [],
          extraction: {
            title: {
              value: null,
              source_quote: null,
              label: 'Missing',
              confidence: null,
              reason: null,
            },
            summary: {
              value: null,
              source_quote: null,
              label: 'Missing',
              confidence: null,
              reason: null,
            },
            expected_behaviour: {
              value: null,
              source_quote: null,
              label: 'Missing',
              confidence: null,
              reason: null,
            },
            actual_behaviour: {
              value: null,
              source_quote: null,
              label: 'Missing',
              confidence: null,
              reason: null,
            },
            frequency: {
              value: null,
              source_quote: null,
              label: 'Missing',
              confidence: null,
              reason: null,
            },
            steps: [],
            environment: [],
            error_messages: [],
          },
          questions: [],
          steps_flagged_for_review: false,
        });
      }
      return jsonResponse({ masked_text: 'Nothing secret here', items: [] });
    });
    renderMaskingReview();
    const user = userEvent.setup();
    await screen.findByText(
      'Nothing was detected automatically. You can still mask something by hand below.',
    );

    // Act
    await user.type(screen.getByLabelText('Mask something else'), 'INTERNAL-42');
    await user.click(screen.getByRole('button', { name: 'Mask' }));
    await user.click(screen.getByRole('button', { name: 'Run analysis' }));

    // Assert
    await waitFor(() => expect(screen.getByText('Analysis page')).toBeInTheDocument());
    expect(analyzeBody).toEqual({ restore_values: [], manual_mask_values: ['INTERNAL-42'] });
  });
});
