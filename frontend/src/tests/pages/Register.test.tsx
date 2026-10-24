import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import Register from '@/pages/Register';

function renderRegister() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/register']}>
        <Routes>
          <Route path="/register" element={<Register />} />
          <Route path="/login" element={<div>Login page</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('Register', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('rejects a password under 8 characters before submitting', async () => {
    // Arrange
    renderRegister();
    const user = userEvent.setup();

    // Act
    await user.type(screen.getByLabelText('Email'), 'new@example.com');
    await user.type(screen.getByLabelText('Password'), 'short1');
    await user.click(screen.getByRole('button', { name: 'Create account' }));

    // Assert
    expect(await screen.findByText('Password must be at least 8 characters')).toBeInTheDocument();
  });

  it('shows "Account already exists" when the server returns 409', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify({ detail: 'Account already exists' }), { status: 409 }),
    );
    renderRegister();
    const user = userEvent.setup();

    // Act
    await user.type(screen.getByLabelText('Email'), 'taken@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple');
    await user.click(screen.getByRole('button', { name: 'Create account' }));

    // Assert
    expect(await screen.findByText('Account already exists')).toBeInTheDocument();
  });

  it('navigates to /login after a successful registration', async () => {
    // Arrange
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(
        JSON.stringify({ id: '1', email: 'new@example.com', created_at: '2026-01-01T00:00:00Z' }),
        { status: 201 },
      ),
    );
    renderRegister();
    const user = userEvent.setup();

    // Act
    await user.type(screen.getByLabelText('Email'), 'new@example.com');
    await user.type(screen.getByLabelText('Password'), 'correct-horse-battery-staple');
    await user.click(screen.getByRole('button', { name: 'Create account' }));

    // Assert
    await waitFor(() => expect(screen.getByText('Login page')).toBeInTheDocument());
  });
});
