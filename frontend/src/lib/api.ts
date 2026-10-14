// The single fetch wrapper. Every request goes through here: same-origin
// /api calls, credentials included so the session cookie is always sent,
// and error responses turned into a typed ApiRequestError.

import type { ApiError } from '@/types/api';

export class ApiRequestError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
  }
}

function extractMessage(body: unknown, fallback: string): string {
  const error = body as ApiError | undefined;
  if (!error || error.detail === undefined) return fallback;
  if (typeof error.detail === 'string') return error.detail;
  const [first] = error.detail;
  return first?.msg ?? fallback;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  const body = await response.json().catch(() => undefined);

  if (!response.ok) {
    throw new ApiRequestError(response.status, extractMessage(body, response.statusText));
  }

  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: 'GET' }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: 'PATCH',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
