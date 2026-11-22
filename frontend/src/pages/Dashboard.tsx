// The signed-in home page at "/": where the user's reports stand, the most
// recent ones, the fields they most often leave out (US-30), and the next
// things to do. Every number comes from the user's own reports only.

import {
  ArrowRight,
  BarChart3,
  CheckCircle2,
  FilePlus2,
  FileText,
  GitBranch,
  Hourglass,
  Send,
  type LucideIcon,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { useCurrentUser } from '@/hooks/useAuth';
import { useReportsList } from '@/hooks/useReports';
import { useMissingFields } from '@/hooks/useAnalytics';
import { EmptyState, ErrorState, LoadingState } from '@/components/states';
import { SeverityBadge, StateBadge } from '@/components/StatusBadge';
import { MissingFieldsList } from '@/components/MissingFieldsList';
import type { ReportRead } from '@/types/api';

const RECENT_COUNT = 5;
const MISSING_SHOWN = 5;

interface StatCardProps {
  label: string;
  value: number;
  hint: string;
  icon: LucideIcon;
  tint: string;
}

function StatCard({ label, value, hint, icon: Icon, tint }: StatCardProps) {
  return (
    <div className="card flex items-start justify-between gap-3 p-5">
      <div className="flex flex-col gap-1">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className="text-3xl font-bold tabular-nums">{value}</span>
        <span className="text-xs text-muted-foreground">{hint}</span>
      </div>
      <span className={`flex h-10 w-10 items-center justify-center rounded-xl ${tint}`}>
        <Icon className="h-5 w-5" aria-hidden="true" />
      </span>
    </div>
  );
}

function RecentReports({ reports }: { reports: ReportRead[] }) {
  if (reports.length === 0) {
    return (
      <EmptyState
        title="No reports yet"
        description="Paste a messy bug description and BugTriage turns it into a clean report."
        action={
          <Link to="/reports/new" className="btn-primary mt-2">
            <FilePlus2 className="h-4 w-4" aria-hidden="true" /> Submit your first report
          </Link>
        }
      />
    );
  }
  return (
    <ul className="flex flex-col divide-y divide-border/70">
      {reports.map((report) => (
        <li key={report.id}>
          <Link
            to={`/reports/${report.id}`}
            className="flex flex-col gap-2 rounded-lg px-2 py-3 transition hover:bg-muted/60 sm:flex-row sm:items-center sm:justify-between"
          >
            <span className="flex min-w-0 flex-col">
              <span className="truncate text-sm font-medium">
                {report.title ?? report.original_text.slice(0, 80)}
              </span>
              <span className="text-xs text-muted-foreground">
                {new Date(report.created_at).toLocaleDateString(undefined, {
                  day: 'numeric',
                  month: 'short',
                  year: 'numeric',
                })}
              </span>
            </span>
            <span className="flex shrink-0 gap-2">
              <SeverityBadge severity={report.severity} />
              <StateBadge state={report.state} />
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function Dashboard() {
  const { data: user } = useCurrentUser();
  const reports = useReportsList({});
  const missing = useMissingFields();

  if (reports.isLoading) return <LoadingState label="Loading your dashboard…" />;

  if (reports.error || !reports.data) {
    return (
      <div className="mx-auto max-w-5xl p-6">
        <ErrorState message="Could not load your dashboard. Try again." />
      </div>
    );
  }

  const items = reports.data.items;
  const count = (states: ReportRead['state'][]) =>
    items.filter((report) => states.includes(report.state)).length;
  const name = user?.email.split('@')[0];

  return (
    <div className="mx-auto flex max-w-6xl flex-col gap-6 p-4 sm:p-6">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="eyebrow">Dashboard</p>
          <h1 className="text-2xl font-bold sm:text-3xl">Welcome back{name ? `, ${name}` : ''}</h1>
          <p className="text-sm text-muted-foreground">
            Here is where your bug reports stand today.
          </p>
        </div>
        <Link to="/reports/new" className="btn-primary">
          <FilePlus2 className="h-4 w-4" aria-hidden="true" /> New report
        </Link>
      </div>

      <section
        aria-label="Your reports at a glance"
        className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4"
      >
        <StatCard
          label="Total reports"
          value={items.length}
          hint="Everything you have submitted"
          icon={FileText}
          tint="bg-accent text-primary"
        />
        <StatCard
          label="Waiting for analysis"
          value={count(['Draft'])}
          hint="Drafts not analysed yet"
          icon={Hourglass}
          tint="bg-amber-50 text-amber-600"
        />
        <StatCard
          label="Ready to share"
          value={count(['Analysed', 'Reviewed', 'Exported'])}
          hint="Analysed, reviewed or exported"
          icon={CheckCircle2}
          tint="bg-emerald-50 text-emerald-600"
        />
        <StatCard
          label="Filed on GitHub"
          value={count(['Submitted'])}
          hint="Issues created from your reports"
          icon={Send}
          tint="bg-blue-50 text-blue-600"
        />
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="card flex flex-col gap-4 p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold">Recent reports</h2>
            {items.length > 0 && (
              <Link to="/reports" className="text-sm font-medium text-primary hover:underline">
                View all
              </Link>
            )}
          </div>
          <RecentReports reports={items.slice(0, RECENT_COUNT)} />
        </section>

        <div className="flex flex-col gap-6">
          <section className="card flex flex-col gap-4 p-5">
            <div>
              <h2 className="text-lg font-semibold">Most often missing</h2>
              <p className="text-xs text-muted-foreground">
                Details your analysed reports usually leave out
              </p>
            </div>
            {missing.isLoading && <LoadingState label="Counting missing details…" />}
            {missing.error && <ErrorState message="Could not load missing details." />}
            {missing.data && <MissingFieldsList data={missing.data} limit={MISSING_SHOWN} />}
          </section>

          <section className="card flex flex-col gap-2 p-5">
            <h2 className="text-lg font-semibold">Quick links</h2>
            {[
              { to: '/analytics', label: 'See your charts', icon: BarChart3 },
              { to: '/settings/github', label: 'Connect GitHub', icon: GitBranch },
            ].map(({ to, label, icon: Icon }) => (
              <Link
                key={to}
                to={to}
                className="flex items-center justify-between rounded-lg px-2 py-2 text-sm hover:bg-muted"
              >
                <span className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-primary" aria-hidden="true" />
                  {label}
                </span>
                <ArrowRight className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
              </Link>
            ))}
          </section>
        </div>
      </div>
    </div>
  );
}
