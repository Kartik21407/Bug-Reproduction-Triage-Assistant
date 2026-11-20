// The analytics dashboard (US-29): three charts built only from the
// signed-in user's own reports (criterion 1), and an empty state instead of
// empty charts when there are none yet (criterion 2).

import { Link } from 'react-router-dom';
import { useAnalytics } from '@/hooks/useAnalytics';
import { ErrorState, LoadingState } from '@/components/states';
import { CategoryChart, SeverityChart, WeeklyChart } from '@/components/AnalyticsCharts';

export default function Analytics() {
  const { data, isLoading, error } = useAnalytics();

  if (isLoading) return <LoadingState label="Loading your analytics…" />;

  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <ErrorState message="Could not load your analytics. Try again." />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Analytics</h1>
          {data.total_reports > 0 && (
            <p className="text-sm text-muted-foreground">
              Based on your {data.total_reports} {data.total_reports === 1 ? 'report' : 'reports'}.
            </p>
          )}
        </div>
        <Link to="/" className="text-sm font-medium underline">
          Home
        </Link>
      </div>

      {data.total_reports === 0 ? (
        <div className="flex flex-col items-start gap-3 rounded-md border p-6">
          <p className="text-sm">
            You have no reports yet, so there is nothing to chart. Your charts appear here once you
            submit your first report.
          </p>
          <Link
            to="/reports/new"
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          >
            Submit a report
          </Link>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <SeverityChart data={data.by_severity} />
          <CategoryChart data={data.by_category} />
          <div className="md:col-span-2">
            <WeeklyChart data={data.by_week} />
          </div>
        </div>
      )}
    </div>
  );
}
