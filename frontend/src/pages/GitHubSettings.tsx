// Connect a GitHub token and choose a repository (US-26). The token is typed
// once, sent once, and never shown again: the server returns only the
// account it belongs to (criterion 3).

import { useState } from 'react';
import { Link } from 'react-router-dom';
import {
  useChooseRepository,
  useConnectGithub,
  useDisconnectGithub,
  useGithubConnection,
  useGithubRepositories,
} from '@/hooks/useGithub';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';

function message(error: unknown, fallback: string): string {
  return error instanceof ApiRequestError ? error.message : fallback;
}

export default function GitHubSettings() {
  const [token, setToken] = useState('');
  const [chosen, setChosen] = useState('');
  const { data: connection, isLoading, error } = useGithubConnection();
  const connect = useConnectGithub();
  const disconnect = useDisconnectGithub();
  const choose = useChooseRepository();
  const repositories = useGithubRepositories({ enabled: Boolean(connection?.connected) });

  if (isLoading) return <LoadingState label="Loading GitHub settings…" />;
  if (error || !connection) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorState message="Could not load your GitHub settings. Try again." />
      </div>
    );
  }

  const submitToken = (event: React.FormEvent) => {
    event.preventDefault();
    if (!token.trim()) return;
    connect.mutate(token, { onSuccess: () => setToken('') });
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-8 p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">GitHub</h1>
        <Link to="/" className="text-sm font-medium underline">
          Home
        </Link>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">Token</h2>
        {connection.connected ? (
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border bg-card p-3">
            <p className="text-sm">
              Connected as <span className="font-medium">{connection.login}</span>
            </p>
            <button
              type="button"
              onClick={() => disconnect.mutate()}
              disabled={disconnect.isPending}
              className="btn-secondary px-3 py-1.5 text-xs"
            >
              Disconnect
            </button>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">Not connected.</p>
        )}

        <form onSubmit={submitToken} className="flex flex-col gap-2">
          <label htmlFor="github-token" className="text-sm font-medium">
            {connection.connected ? 'Replace the token' : 'Fine-grained personal access token'}
          </label>
          <input
            id="github-token"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(event) => setToken(event.target.value)}
            className="rounded-lg border px-3 py-2 text-sm"
          />
          <p className="text-xs text-muted-foreground">
            Create one on GitHub under Settings, Developer settings, Fine-grained tokens. Give it
            access to the repositories you want to file in, with &quot;Issues: Read and write&quot;.
            It is stored encrypted and never shown again.
          </p>
          {connect.error && (
            <ErrorState message={message(connect.error, 'Could not connect. Try again.')} />
          )}
          <button
            type="submit"
            disabled={connect.isPending || !token.trim()}
            className="self-start btn-primary px-3 py-2 text-sm"
          >
            {connect.isPending ? 'Checking…' : 'Connect'}
          </button>
        </form>
      </section>

      {connection.connected && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Repository</h2>
          {connection.repository && (
            <p className="text-sm">
              Issues are filed in <span className="font-medium">{connection.repository}</span>
            </p>
          )}
          {repositories.isLoading && <LoadingState label="Loading repositories…" />}
          {repositories.error && (
            <ErrorState
              message={message(repositories.error, 'Could not load repositories. Try again.')}
            />
          )}
          {repositories.data && repositories.data.length === 0 && (
            <p className="text-sm text-muted-foreground">
              This token cannot file issues in any repository yet. Check its repository access and
              its &quot;Issues&quot; permission on GitHub.
            </p>
          )}
          {repositories.data && repositories.data.length > 0 && (
            <div className="flex flex-wrap items-end gap-2">
              <div className="flex flex-col gap-1">
                <label htmlFor="github-repository" className="text-sm font-medium">
                  Repository to file issues in
                </label>
                <select
                  id="github-repository"
                  value={chosen || connection.repository || ''}
                  onChange={(event) => setChosen(event.target.value)}
                  className="rounded-lg border px-3 py-2 text-sm"
                >
                  <option value="" disabled>
                    Choose a repository
                  </option>
                  {repositories.data.map((repository) => (
                    <option key={repository.full_name} value={repository.full_name}>
                      {repository.full_name}
                      {repository.private ? ' (private)' : ''}
                    </option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={() => chosen && choose.mutate(chosen)}
                disabled={!chosen || choose.isPending}
                className="btn-secondary px-3 py-2 text-sm"
              >
                Save
              </button>
            </div>
          )}
          {choose.error && (
            <ErrorState message={message(choose.error, 'Could not save. Try again.')} />
          )}
        </section>
      )}
    </div>
  );
}
