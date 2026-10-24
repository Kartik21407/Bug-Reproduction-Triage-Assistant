import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import NewReport from '@/pages/NewReport';

function renderNewReport() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <NewReport />
    </QueryClientProvider>,
  );
}

describe('NewReport', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('shows an inline error and does not submit when the text is too short', async () => {
    // Arrange
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderNewReport();
    const user = userEvent.setup();

    // Act
    await user.type(screen.getByLabelText('Bug description'), 'too short');
    await user.click(screen.getByRole('button', { name: 'Submit' }));

    // Assert
    expect(await screen.findByText('Enter at least 20 characters')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('does not submit empty input', async () => {
    // Arrange
    const fetchSpy = vi.spyOn(globalThis, 'fetch');
    renderNewReport();
    const user = userEvent.setup();

    // Act
    await user.click(screen.getByRole('button', { name: 'Submit' }));

    // Assert
    expect(await screen.findByText('Enter at least 20 characters')).toBeInTheDocument();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it('submits valid text and shows a confirmation', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({
          id: '1',
          title: null,
          original_text: 'This description is definitely long enough to pass.',
          logs: null,
          state: 'Draft',
          severity: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        }),
        { status: 201 },
      ),
    );
    renderNewReport();
    const user = userEvent.setup();

    // Act
    await user.type(
      screen.getByLabelText('Bug description'),
      'This description is definitely long enough to pass.',
    );
    await user.click(screen.getByRole('button', { name: 'Submit' }));

    // Assert
    expect(await screen.findByText('Report submitted.')).toBeInTheDocument();
  });

  describe('Clear button', () => {
    afterEach(() => {
      vi.restoreAllMocks();
    });

    it('empties the box after the user confirms', async () => {
      // Arrange
      vi.spyOn(window, 'confirm').mockReturnValue(true);
      renderNewReport();
      const user = userEvent.setup();
      const textbox = screen.getByLabelText('Bug description') as HTMLTextAreaElement;

      // Act
      await user.type(textbox, 'Some text that will be cleared afterwards.');
      await user.click(screen.getByRole('button', { name: 'Clear' }));

      // Assert
      expect(window.confirm).toHaveBeenCalled();
      await waitFor(() => expect(textbox.value).toBe(''));
    });

    it('keeps the text when the user cancels the confirmation', async () => {
      // Arrange
      vi.spyOn(window, 'confirm').mockReturnValue(false);
      renderNewReport();
      const user = userEvent.setup();
      const textbox = screen.getByLabelText('Bug description') as HTMLTextAreaElement;

      // Act
      await user.type(textbox, 'Some text that should not be cleared.');
      await user.click(screen.getByRole('button', { name: 'Clear' }));

      // Assert
      expect(textbox.value).toBe('Some text that should not be cleared.');
    });
  });

  it('shows a live character counter for the description', async () => {
    // Arrange
    renderNewReport();
    const user = userEvent.setup();

    // Act
    await user.type(screen.getByLabelText('Bug description'), 'twelve chars');

    // Assert
    expect(screen.getByText('12 / 10,000')).toBeInTheDocument();
  });
});
