// Report history with sorting, severity and status filters, keyword search
// and an empty state (US-06).

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useReportsList } from '@/hooks/useReports';
import { EmptyState, ErrorState, LoadingState } from '@/components/states';
import type { ReportState, Severity } from '@/types/api';

const SEVERITIES: Severity[] = ['Critical', 'High', 'Medium', 'Low'];
const STATES: ReportState[] = ['Draft', 'Analysed', 'Reviewed', 'Exported', 'Submitted'];

function useDebouncedValue(value: string, delayMs: number): string {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(timer);
  }, [value, delayMs]);
  return debounced;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  });
}

export default function History() {
  const [searchInput, setSearchInput] = useState('');
  const [severity, setSeverity] = useState<Severity | ''>('');
  const [state, setState] = useState<ReportState | ''>('');
  const search = useDebouncedValue(searchInput, 300);

  const hasActiveFilters = Boolean(search.trim() || severity || state);

  const { data, isLoading, isError } = useReportsList({
    search: search || undefined,
    severity: severity || undefined,
    state: state || undefined,
  });

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">History</h1>
        <Link to="/reports/new" className="text-sm font-medium underline">
          New report
        </Link>
      </div>

      <div className="flex flex-wrap gap-3">
        <div className="flex flex-1 flex-col gap-1">
          <label htmlFor="search" className="text-sm font-medium">
            Search
          </label>
          <input
            id="search"
            type="search"
            placeholder="Search title or description"
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            className="rounded-md border px-3 py-2 text-sm"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="severity" className="text-sm font-medium">
            Severity
          </label>
          <select
            id="severity"
            value={severity}
            onChange={(event) => setSeverity(event.target.value as Severity | '')}
            className="rounded-md border px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {SEVERITIES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="state" className="text-sm font-medium">
            Status
          </label>
          <select
            id="state"
            value={state}
            onChange={(event) => setState(event.target.value as ReportState | '')}
            className="rounded-md border px-3 py-2 text-sm"
          >
            <option value="">All</option>
            {STATES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Severity and status are real columns and real filters, but every
          report is Draft with no severity this sprint, since triage runs in
          Sprint 3. The filters stay visible and usable rather than hidden,
          and this line says why the results may look sparse. */}
      <p className="text-xs text-muted-foreground">
        Severity is not assigned yet; that starts once triage is built. Every report is currently
        Draft.
      </p>

      {isLoading && <LoadingState label="Loading your reports…" />}
      {isError && <ErrorState message="Could not load your reports. Try again." />}

      {data && data.items.length === 0 && !hasActiveFilters && (
        <EmptyState
          title="No reports yet"
          description="Submit your first bug report to see it here."
          action={
            <Link
              to="/reports/new"
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
            >
              Submit a report
            </Link>
          }
        />
      )}

      {data && data.items.length === 0 && hasActiveFilters && (
        <EmptyState
          title="No reports match"
          description="Try a different search term or clear the filters."
        />
      )}

      {data && data.items.length > 0 && (
        <ul className="flex flex-col divide-y rounded-lg border">
          {data.items.map((report) => (
            <li key={report.id}>
              <Link
                to={`/reports/${report.id}`}
                className="flex items-center justify-between gap-4 p-4 hover:bg-muted"
              >
                <div className="flex flex-col gap-0.5">
                  <span className="font-medium">{report.title ?? 'Untitled report'}</span>
                  <span className="text-xs text-muted-foreground">
                    {report.severity ?? 'Not yet triaged'} · {report.state}
                  </span>
                </div>
                <span className="text-sm text-muted-foreground">
                  {formatDate(report.created_at)}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
