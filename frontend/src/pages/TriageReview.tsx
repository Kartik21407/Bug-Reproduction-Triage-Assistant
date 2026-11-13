// Triage and duplicates (US-15, US-16, US-17, US-20): the suggested
// severity, priority, category and reproducibility, each editable, and the
// most similar existing issues.

import { Link, useParams } from 'react-router-dom';
import { useReport } from '@/hooks/useReports';
import { useOverrideTriage, useTriage } from '@/hooks/useTriage';
import { useDuplicates, useFindDuplicates } from '@/hooks/useDuplicates';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';
import { TriagePanel } from '@/components/TriagePanel';
import { DuplicateCandidateList } from '@/components/DuplicateCandidateList';

export default function TriageReview() {
  const { id } = useParams<{ id: string }>();
  const reportId = id ?? '';

  const { data: report, isLoading: isReportLoading, error: reportError } = useReport(reportId);
  const isAnalysed = report !== undefined && report.state !== 'Draft';
  const {
    data: triage,
    isLoading: isTriageLoading,
    error: triageError,
  } = useTriage(reportId, { enabled: isAnalysed });
  const { data: duplicates, error: duplicatesError } = useDuplicates(reportId);
  const overrideTriage = useOverrideTriage(reportId);
  const findDuplicates = useFindDuplicates(reportId);

  if (isReportLoading) {
    return <LoadingState label="Loading triage…" />;
  }

  if (reportError instanceof ApiRequestError && reportError.status === 404) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState message="Report not found." />
      </div>
    );
  }

  if (reportError || !report) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState message="Could not load this report. Try again." />
      </div>
    );
  }

  if (!isAnalysed) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
        <h1 className="text-xl font-semibold">Triage</h1>
        <p className="text-sm text-muted-foreground">
          This report has not been analysed yet. Triage is suggested from the analysed report.
        </p>
        <Link
          to={`/reports/${reportId}/mask`}
          className="self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
        >
          Review and analyse
        </Link>
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">{report.title ?? 'Untitled report'}</h1>
          <p className="text-sm text-muted-foreground">Triage and similar issues</p>
        </div>
        <div className="flex shrink-0 gap-3">
          <Link
            to={`/reports/${reportId}/analysis`}
            className="rounded-md border px-3 py-2 text-sm font-medium"
          >
            Back to analysis
          </Link>
          <Link
            to={`/reports/${reportId}/report`}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          >
            View report
          </Link>
        </div>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">Suggested triage</h2>
        {isTriageLoading && <LoadingState label="Loading suggestions…" />}
        {triageError && <ErrorState message="Could not load the triage suggestions. Try again." />}
        {overrideTriage.error && <ErrorState message="Could not save that change. Try again." />}
        {triage && (
          <TriagePanel
            triage={triage}
            isSaving={overrideTriage.isPending}
            onChange={(field, value) => overrideTriage.mutate({ field, value })}
          />
        )}
      </section>

      <section className="flex flex-col gap-3">
        <div className="flex items-center justify-between gap-3">
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">
            Similar existing issues
          </h2>
          <button
            type="button"
            onClick={() => findDuplicates.mutate()}
            disabled={findDuplicates.isPending}
            className="shrink-0 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-60"
          >
            {findDuplicates.isPending
              ? 'Searching…'
              : duplicates?.searched
                ? 'Search again'
                : 'Find similar issues'}
          </button>
        </div>
        {duplicatesError && <ErrorState message="Could not load similar issues. Try again." />}
        {findDuplicates.error && (
          <ErrorState
            message={
              findDuplicates.error instanceof ApiRequestError
                ? findDuplicates.error.message
                : 'The search failed. Try again.'
            }
          />
        )}
        {duplicates && !duplicates.searched && (
          <p className="text-sm text-muted-foreground">
            Not searched yet. Find similar issues to check this report against existing ones before
            filing it.
          </p>
        )}
        {duplicates?.searched && (
          <DuplicateCandidateList
            candidates={duplicates.candidates}
            comparedCount={duplicates.compared_count}
          />
        )}
      </section>
    </div>
  );
}
