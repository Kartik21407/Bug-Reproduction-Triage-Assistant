// The administrator page at /admin: deactivate or reactivate accounts
// (US-03), tune the duplicate thresholds (US-31), and control the automatic
// import of a repository's open issues (US-28). Only administrators reach
// it; the server refuses everyone else as well.

import { useState } from 'react';
import { RefreshCw, RotateCcw } from 'lucide-react';
import {
  useAdminUsers,
  useCorpusSync,
  useResetThresholds,
  useRunSync,
  useSaveSyncRepository,
  useSaveThresholds,
  useSetUserActive,
  useThresholds,
} from '@/hooks/useAdmin';
import { useCurrentUser } from '@/hooks/useAuth';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';
import type { CorpusSyncRead, DuplicateThresholds } from '@/types/api';

function message(error: unknown, fallback: string): string {
  return error instanceof ApiRequestError ? error.message : fallback;
}

function UsersSection() {
  const { data: me } = useCurrentUser();
  const users = useAdminUsers();
  const setActive = useSetUserActive();

  return (
    <section aria-labelledby="users-heading" className="card flex flex-col gap-4 p-5">
      <div>
        <h2 id="users-heading" className="text-lg font-semibold">
          Accounts
        </h2>
        <p className="text-sm text-muted-foreground">
          A deactivated account cannot sign in. Its reports are kept exactly as they are.
        </p>
      </div>
      {users.isLoading && <LoadingState label="Loading accounts…" />}
      {users.error && <ErrorState message={message(users.error, 'Could not load accounts.')} />}
      {setActive.error && (
        <ErrorState message={message(setActive.error, 'Could not change that account.')} />
      )}
      {users.data && (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Email
                </th>
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Reports
                </th>
                <th scope="col" className="py-2 pr-4 font-semibold">
                  Status
                </th>
                <th scope="col" className="py-2 font-semibold">
                  <span className="sr-only">Action</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {users.data.map((user) => {
                const isMe = user.id === me?.id;
                return (
                  <tr key={user.id} className="border-b last:border-b-0">
                    <td className="py-3 pr-4">
                      <span className="font-medium">{user.email}</span>
                      {user.is_admin && (
                        <span className="ml-2 rounded-full bg-accent px-2 py-0.5 text-[11px] font-semibold text-accent-foreground">
                          Admin
                        </span>
                      )}
                    </td>
                    <td className="py-3 pr-4 tabular-nums">{user.report_count}</td>
                    <td className="py-3 pr-4">
                      {user.is_active ? (
                        <span className="text-emerald-700">Active</span>
                      ) : (
                        <span className="text-destructive">Deactivated</span>
                      )}
                    </td>
                    <td className="py-3 text-right">
                      {isMe ? (
                        <span className="text-xs text-muted-foreground">You</span>
                      ) : (
                        <button
                          type="button"
                          disabled={setActive.isPending}
                          onClick={() =>
                            setActive.mutate({ userId: user.id, isActive: !user.is_active })
                          }
                          aria-label={`${user.is_active ? 'Deactivate' : 'Reactivate'} ${user.email}`}
                          className="btn-secondary px-3 py-1 text-xs"
                        >
                          {user.is_active ? 'Deactivate' : 'Reactivate'}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function ThresholdsForm({ current }: { current: DuplicateThresholds }) {
  const [likely, setLikely] = useState(String(current.likely));
  const [possible, setPossible] = useState(String(current.possible));
  const [localError, setLocalError] = useState<string | null>(null);
  const save = useSaveThresholds();
  const reset = useResetThresholds();

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    setLocalError(null);
    const likelyValue = Number(likely);
    const possibleValue = Number(possible);
    if (
      likely.trim() === '' ||
      possible.trim() === '' ||
      Number.isNaN(likelyValue + possibleValue)
    ) {
      setLocalError('Enter both thresholds as numbers between 0 and 1.');
      return;
    }
    save.mutate({ likely: likelyValue, possible: possibleValue });
  };

  const resetToDefaults = () =>
    reset.mutate(undefined, {
      onSuccess: (result) => {
        setLikely(String(result.likely));
        setPossible(String(result.possible));
      },
    });

  const error = localError ?? (save.error ? message(save.error, 'Could not save.') : null);

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="flex flex-col gap-1.5">
          <label htmlFor="likely-threshold" className="text-sm font-medium">
            Likely duplicate at or above
          </label>
          <input
            id="likely-threshold"
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0"
            max="1"
            value={likely}
            onChange={(event) => setLikely(event.target.value)}
            className="field"
          />
        </div>
        <div className="flex flex-col gap-1.5">
          <label htmlFor="possible-threshold" className="text-sm font-medium">
            Possible duplicate at or above
          </label>
          <input
            id="possible-threshold"
            type="number"
            inputMode="decimal"
            step="0.01"
            min="0"
            max="1"
            value={possible}
            onChange={(event) => setPossible(event.target.value)}
            className="field"
          />
        </div>
      </div>
      <p className="text-xs text-muted-foreground">
        Both between 0 and 1, the possible threshold below the likely one. Defaults are{' '}
        {current.default_likely} and {current.default_possible}. Changes apply to searches run
        afterwards.
      </p>
      {error && <ErrorState message={error} />}
      {save.isSuccess && !error && (
        <p role="status" className="text-sm text-emerald-700">
          Saved. New searches use these thresholds.
        </p>
      )}
      <div className="flex flex-wrap gap-2">
        <button type="submit" disabled={save.isPending} className="btn-primary">
          {save.isPending ? 'Saving…' : 'Save thresholds'}
        </button>
        {current.customised && (
          <button
            type="button"
            onClick={resetToDefaults}
            disabled={reset.isPending}
            className="btn-secondary"
          >
            <RotateCcw className="h-4 w-4" aria-hidden="true" /> Reset to defaults
          </button>
        )}
      </div>
    </form>
  );
}

function ThresholdsSection() {
  const thresholds = useThresholds();
  return (
    <section aria-labelledby="thresholds-heading" className="card flex flex-col gap-4 p-5">
      <div>
        <h2 id="thresholds-heading" className="text-lg font-semibold">
          Duplicate thresholds
        </h2>
        <p className="text-sm text-muted-foreground">
          How similar an existing issue must be to be shown as a Likely or Possible duplicate.
        </p>
      </div>
      {thresholds.isLoading && <LoadingState label="Loading thresholds…" />}
      {thresholds.error && (
        <ErrorState message={message(thresholds.error, 'Could not load thresholds.')} />
      )}
      {thresholds.data && <ThresholdsForm current={thresholds.data} />}
    </section>
  );
}

const STATUS_TEXT: Record<string, string> = {
  idle: 'Not run yet',
  running: 'Importing…',
  paused: 'Paused by GitHub’s rate limit',
  complete: 'Up to date',
  failed: 'Stopped with an error',
};

function SyncStatus({ sync }: { sync: CorpusSyncRead }) {
  const state = sync.state;
  if (!sync.repository) {
    return (
      <p className="text-sm text-muted-foreground">
        No repository is set, so the automatic import is off.
      </p>
    );
  }
  return (
    <dl className="grid gap-3 text-sm sm:grid-cols-4">
      <div>
        <dt className="text-xs text-muted-foreground">Status</dt>
        <dd className="font-medium">
          {sync.running ? STATUS_TEXT.running : STATUS_TEXT[state?.status ?? 'idle']}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Pages fetched</dt>
        <dd className="font-medium tabular-nums">{state?.pages_done ?? 0}</dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">New / updated</dt>
        <dd className="font-medium tabular-nums">
          {state?.imported ?? 0} / {state?.updated ?? 0}
        </dd>
      </div>
      <div>
        <dt className="text-xs text-muted-foreground">Schedule</dt>
        <dd className="font-medium">
          {sync.interval_minutes > 0 ? `Every ${sync.interval_minutes} min` : 'Off'}
        </dd>
      </div>
      {state?.message && (
        <p className="text-sm text-muted-foreground sm:col-span-4">{state.message}</p>
      )}
    </dl>
  );
}

function CorpusSyncSection() {
  const sync = useCorpusSync();
  const saveRepository = useSaveSyncRepository();
  const run = useRunSync();
  const [repository, setRepository] = useState<string | null>(null);
  const shown = repository ?? sync.data?.repository ?? '';

  const save = (event: React.FormEvent) => {
    event.preventDefault();
    saveRepository.mutate(shown.trim(), { onSuccess: () => setRepository(null) });
  };

  const error = saveRepository.error ?? run.error;

  return (
    <section aria-labelledby="sync-heading" className="card flex flex-col gap-4 p-5">
      <div>
        <h2 id="sync-heading" className="text-lg font-semibold">
          Automatic issue import
        </h2>
        <p className="text-sm text-muted-foreground">
          Keeps duplicate search current by importing a GitHub repository’s open issues, page by
          page. If GitHub’s rate limit stops it, nothing is lost and it resumes where it stopped.
        </p>
      </div>
      <form onSubmit={save} className="flex flex-wrap items-end gap-2">
        <div className="flex min-w-[16rem] flex-1 flex-col gap-1.5">
          <label htmlFor="sync-repository" className="text-sm font-medium">
            Repository (owner/name)
          </label>
          <input
            id="sync-repository"
            value={shown}
            onChange={(event) => setRepository(event.target.value)}
            placeholder="nextcloud/server"
            className="field"
          />
        </div>
        <button type="submit" disabled={saveRepository.isPending} className="btn-secondary">
          Save
        </button>
        <button
          type="button"
          onClick={() => run.mutate()}
          disabled={!sync.data?.repository || sync.data.running || run.isPending}
          className="btn-primary"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" /> Import now
        </button>
      </form>
      {error && <ErrorState message={message(error, 'Something went wrong. Try again.')} />}
      {sync.isLoading && <LoadingState label="Loading import status…" />}
      {sync.data && <SyncStatus sync={sync.data} />}
    </section>
  );
}

export default function Admin() {
  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-4 sm:p-6">
      <div>
        <p className="eyebrow">Administration</p>
        <h1 className="text-2xl font-bold sm:text-3xl">Admin</h1>
        <p className="text-sm text-muted-foreground">
          Accounts, duplicate detection settings and the shared issue corpus.
        </p>
      </div>
      <UsersSection />
      <ThresholdsSection />
      <CorpusSyncSection />
    </div>
  );
}
