import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import GitHubIssue from '@/pages/GitHubIssue';
import type { IssuePreview } from '@/types/api';

const ISSUE_URL = 'https://github.com/octo/app/issues/12';

function makePreview(overrides: Partial<IssuePreview> = {}): IssuePreview {
  return {
    repository: 'octo/app',
    title: 'Login crashes on a wrong password',
    body: '## Summary\n\nLogin closes instead of showing an error\n',
    labels: ['bug'],
    likely_duplicates: [],
    warnings: [],
    issue_url: null,
    ...overrides,
  };
}

function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status });
}

function mockFetch(preview: IssuePreview, onCreate?: () => Response) {
  const posts: unknown[] = [];
  vi.spyOn(globalThis, 'fetch').mockImplementation(async (url, init) => {
    if (init?.method === 'POST') {
      posts.push(JSON.parse(init.body as string));
      return (
        onCreate?.() ?? jsonResponse({ issue_url: ISSUE_URL, issue_number: 12, created: true })
      );
    }
    if (String(url).endsWith('/github/preview')) return jsonResponse(preview);
    return jsonResponse({ detail: 'unexpected' }, 500);
  });
  return posts;
}

function renderIssue(id = 'report-1') {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/reports/${id}/github`]}>
        <Routes>
          <Route path="/reports/:id/github" element={<GitHubIssue />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('GitHubIssue', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows the exact title, body and labels that will be sent', async () => {
    // Arrange
    mockFetch(makePreview());

    // Act
    renderIssue();

    // Assert: US-27 criterion 1
    expect(await screen.findByText('Login crashes on a wrong password')).toBeInTheDocument();
    expect(screen.getByText('bug')).toBeInTheDocument();
    expect(screen.getByText(/Login closes instead of showing an error/).textContent).toBe(
      '## Summary\n\nLogin closes instead of showing an error\n',
    );
  });

  it('sends nothing until Confirm is clicked', async () => {
    // Arrange
    const posts = mockFetch(makePreview());
    renderIssue();
    const user = userEvent.setup();
    const confirm = await screen.findByRole('button', { name: 'Confirm and file' });
    expect(posts).toEqual([]);

    // Act
    await user.click(confirm);

    // Assert: US-27 criteria 2 and 5
    expect(await screen.findByRole('link', { name: ISSUE_URL })).toHaveAttribute('href', ISSUE_URL);
    expect(posts).toEqual([{ acknowledge_likely_duplicates: false }]);
    expect(screen.queryByRole('button', { name: 'Confirm and file' })).not.toBeInTheDocument();
  });

  it('needs a Likely duplicate acknowledged before Confirm', async () => {
    // Arrange
    const posts = mockFetch(
      makePreview({
        likely_duplicates: [
          { title: 'Login page crashes', url: 'https://github.com/octo/app/issues/7', score: 0.91 },
        ],
      }),
    );
    renderIssue();
    const user = userEvent.setup();
    const confirm = await screen.findByRole('button', { name: 'Confirm and file' });

    // Act and Assert: US-27 criterion 3
    expect(confirm).toBeDisabled();
    await user.click(screen.getByRole('checkbox', { name: /still want to file this report/ }));
    expect(confirm).toBeEnabled();
    await user.click(confirm);
    await screen.findByRole('link', { name: ISSUE_URL });
    expect(posts).toEqual([{ acknowledge_likely_duplicates: true }]);
  });

  it('cannot be confirmed twice while filing', async () => {
    // Arrange
    let finish: (response: Response) => void = () => {};
    const posts = mockFetch(
      makePreview(),
      () => new Promise<Response>((resolve) => (finish = resolve)) as unknown as Response,
    );
    renderIssue();
    const user = userEvent.setup();
    const confirm = await screen.findByRole('button', { name: 'Confirm and file' });

    // Act
    await user.click(confirm);
    const filing = await screen.findByRole('button', { name: 'Filing…' });
    await user.click(filing);

    // Assert: US-27 criterion 4
    expect(filing).toBeDisabled();
    expect(posts).toHaveLength(1);
    finish(jsonResponse({ issue_url: ISSUE_URL, issue_number: 12, created: true }));
    await screen.findByRole('link', { name: ISSUE_URL });
  });

  it('keeps the draft and shows the error when filing fails', async () => {
    // Arrange
    const detail = 'GitHub is rate limiting requests. Try again in a few minutes.';
    mockFetch(makePreview(), () => jsonResponse({ detail }, 503));
    renderIssue();
    const user = userEvent.setup();

    // Act
    await user.click(await screen.findByRole('button', { name: 'Confirm and file' }));

    // Assert: US-27 criterion 6
    expect(await screen.findByText(detail)).toBeInTheDocument();
    expect(screen.getByText('Login crashes on a wrong password')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Confirm and file' })).toBeEnabled();
  });

  it('shows the stored link for a report that was already filed', async () => {
    // Arrange
    mockFetch(makePreview({ issue_url: ISSUE_URL }));

    // Act
    renderIssue();

    // Assert
    expect(await screen.findByRole('link', { name: ISSUE_URL })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirm and file' })).not.toBeInTheDocument();
  });

  it('points to GitHub settings when no repository is chosen', async () => {
    // Arrange
    mockFetch(makePreview({ repository: null }));

    // Act
    renderIssue();

    // Assert
    expect(await screen.findByRole('link', { name: 'GitHub settings' })).toHaveAttribute(
      'href',
      '/settings/github',
    );
    expect(screen.getByRole('button', { name: 'Confirm and file' })).toBeDisabled();
  });
});
