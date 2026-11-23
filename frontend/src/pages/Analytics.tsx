// The analytics page (US-29, US-30): three charts built only from the
// signed-in user's own reports (US-29 criterion 1), an empty state instead
// of empty charts when there are none yet (criterion 2), and the fields
// most often missing as a ranked list with counts (US-30).

import { Link } from 'react-router-dom';
import { useAnalytics, useMissingFields } from '@/hooks/useAnalytics';
import { ErrorState, LoadingState } from '@/components/states';
import { CategoryChart, SeverityChart, WeeklyChart } from '@/components/AnalyticsCharts';
import { MissingFieldsList } from '@/components/MissingFieldsList';

export default function Analytics() {
  const { data, isLoading, error } = useAnalytics();
  const missing = useMissingFields();

  if (isLoading) return <LoadingState label="Loading your analytics…" />;

  if (error || !data) {
    return (
      <div className="mx-auto max-w-4xl p-6">
        <ErrorState message="Could not load your analytics. Try again." />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6 p-4 sm:p-6">
      <div>
        <p className="eyebrow">Insights</p>
        <h1 className="text-2xl font-bold sm:text-3xl">Analytics</h1>
        {data.total_reports > 0 && (
          <p className="text-sm text-muted-foreground">
            Based on your {data.total_reports} {data.total_reports === 1 ? 'report' : 'reports'}.
          </p>
        )}
      </div>

      {data.total_reports === 0 ? (
        <div className="card flex flex-col items-start gap-3 p-6">
          <p className="text-sm">
            You have no reports yet, so there is nothing to chart. Your charts appear here once you
            submit your first report.
          </p>
          <Link to="/reports/new" className="btn-primary">
            Submit a report
          </Link>
        </div>
      ) : (
        <>
          <div className="grid gap-4 md:grid-cols-2">
            <SeverityChart data={data.by_severity} />
            <CategoryChart data={data.by_category} />
            <div className="md:col-span-2">
              <WeeklyChart data={data.by_week} />
            </div>
          </div>
          <section aria-labelledby="missing-heading" className="card flex flex-col gap-4 p-5">
            <div>
              <h2 id="missing-heading" className="text-sm font-semibold">
                Most commonly missing fields
              </h2>
              <p className="text-xs text-muted-foreground">
                How many of your analysed reports leave each detail out, most often first.
              </p>
            </div>
            {missing.error && <ErrorState message="Could not load missing fields. Try again." />}
            {missing.data && <MissingFieldsList data={missing.data} />}
          </section>
        </>
      )}
    </div>
  );
}
