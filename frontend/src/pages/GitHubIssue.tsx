// Preview a report as a GitHub issue, then file it only on Confirm (US-27).
// The preview is exactly what is sent (criterion 1); nothing reaches GitHub
// before Confirm (criterion 2); a Likely duplicate has to be acknowledged
// first (criterion 3); Confirm cannot run twice at once (criterion 4); a
// failure leaves the draft as it was and says why (criterion 6).

import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useCreateIssue, useIssuePreview } from '@/hooks/useGithub';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';

export default function GitHubIssue() {
  const { id } = useParams<{ id: string }>();
  const reportId = id ?? '';
  const [acknowledged, setAcknowledged] = useState(false);
  const { data: preview, isLoading, error } = useIssuePreview(reportId);
  const createIssue = useCreateIssue(reportId);

  if (isLoading) return <LoadingState label="Preparing the issue…" />;

  if (error instanceof ApiRequestError && error.status === 404) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState message="Report not found." />
      </div>
    );
  }

  if (error || !preview) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState message="Could not prepare the issue. Try again." />
      </div>
    );
  }

  const filedUrl = createIssue.data?.issue_url ?? preview.issue_url;
  const needsAcknowledgement = preview.likely_duplicates.length > 0;
  const canConfirm =
    Boolean(preview.repository) &&
    !filedUrl &&
    (!needsAcknowledgement || acknowledged) &&
    !createIssue.isPending;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">File on GitHub</h1>
        <Link
          to={`/reports/${reportId}/report`}
          className="shrink-0 rounded-md border px-3 py-2 text-sm font-medium"
        >
          Back to report
        </Link>
      </div>

      {filedUrl && (
        <p className="rounded-md border border-green-400 bg-green-50 p-3 text-sm text-green-900">
          Filed as{' '}
          <a href={filedUrl} target="_blank" rel="noreferrer" className="font-medium underline">
            {filedUrl}
          </a>
        </p>
      )}

      {!preview.repository && !filedUrl && (
        <p className="text-sm">
          Connect GitHub and choose a repository first, in{' '}
          <Link to="/settings/github" className="font-medium underline">
            GitHub settings
          </Link>
          .
        </p>
      )}

      {preview.warnings.length > 0 && (
        <div className="rounded-md border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">This report is incomplete</p>
          <ul className="list-disc pl-5">
            {preview.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      <section aria-label="Issue preview" className="flex flex-col gap-3 rounded-md border p-4">
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground">Repository</span>
          <span className="text-sm">{preview.repository ?? 'None chosen'}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground">Title</span>
          <span className="text-sm font-medium">{preview.title}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground">Labels</span>
          <span className="text-sm">{preview.labels.join(', ') || 'None'}</span>
        </div>
        <div className="flex flex-col gap-0.5">
          <span className="text-xs font-medium text-muted-foreground">Body (Markdown)</span>
          <pre className="max-h-96 overflow-auto whitespace-pre-wrap rounded-md border p-3 font-mono text-xs">
            {preview.body}
          </pre>
        </div>
      </section>

      {needsAcknowledgement && !filedUrl && (
        <div className="flex flex-col gap-2 rounded-md border border-amber-400 p-3">
          <p className="text-sm font-medium">This report has likely duplicates</p>
          <ul className="list-disc pl-5 text-sm">
            {preview.likely_duplicates.map((duplicate) => (
              <li key={duplicate.url}>
                {duplicate.url.startsWith('/') ? (
                  <Link to={duplicate.url} className="underline">
                    {duplicate.title}
                  </Link>
                ) : (
                  <a href={duplicate.url} target="_blank" rel="noreferrer" className="underline">
                    {duplicate.title}
                  </a>
                )}{' '}
                <span className="text-xs text-muted-foreground">
                  similarity {duplicate.score.toFixed(2)}
                </span>
              </li>
            ))}
          </ul>
          <label className="flex items-start gap-2 text-sm">
            <input
              type="checkbox"
              checked={acknowledged}
              onChange={(event) => setAcknowledged(event.target.checked)}
              className="mt-1"
            />
            I have checked these and still want to file this report.
          </label>
        </div>
      )}

      {createIssue.error && (
        <ErrorState
          message={
            createIssue.error instanceof ApiRequestError
              ? createIssue.error.message
              : 'Filing failed. Your report is unchanged; try again.'
          }
        />
      )}

      {!filedUrl && (
        <button
          type="button"
          onClick={() => createIssue.mutate(acknowledged)}
          disabled={!canConfirm}
          className="self-start rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
        >
          {createIssue.isPending ? 'Filing…' : 'Confirm and file'}
        </button>
      )}
    </div>
  );
}
