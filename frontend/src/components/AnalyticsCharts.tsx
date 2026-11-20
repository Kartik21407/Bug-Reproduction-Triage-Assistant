// The three dashboard charts (US-29 criterion 1): reports by severity and by
// category as bars, and reports per week as a line. Each chart is one series,
// so its heading names it and there is no legend. Every chart also has a
// table with the same numbers, so nothing depends on reading the picture.

import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { NamedCount, WeekCount } from '@/types/api';

const SERIES = '#2a78d6';
const GRID = '#e5e4df';
const AXIS = '#52514e';
const TICK = { fill: AXIS, fontSize: 12 };

interface ChartCardProps {
  title: string;
  description: string;
  rows: { label: string; count: number }[];
  firstColumn: string;
  children: React.ReactNode;
}

function ChartCard({ title, description, rows, firstColumn, children }: ChartCardProps) {
  return (
    <section aria-label={title} className="flex flex-col gap-3 rounded-md border p-4">
      <div>
        <h2 className="text-sm font-semibold">{title}</h2>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
      <div className="h-64 w-full" aria-hidden="true">
        {children}
      </div>
      <details>
        <summary className="cursor-pointer text-xs font-medium">Show as a table</summary>
        <table className="mt-2 w-full text-left text-sm">
          <caption className="sr-only">{title}</caption>
          <thead>
            <tr className="border-b">
              <th scope="col" className="py-1 font-medium">
                {firstColumn}
              </th>
              <th scope="col" className="py-1 text-right font-medium">
                Reports
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.label} className="border-b last:border-b-0">
                <td className="py-1">{row.label}</td>
                <td className="py-1 text-right tabular-nums">{row.count}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </section>
  );
}

function CountBars({ data }: { data: NamedCount[] }) {
  return (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, bottom: 0, left: -16 }}>
        <CartesianGrid vertical={false} stroke={GRID} />
        <XAxis dataKey="name" tick={TICK} tickLine={false} axisLine={{ stroke: GRID }} />
        <YAxis allowDecimals={false} tick={TICK} tickLine={false} axisLine={false} />
        <Tooltip cursor={{ fill: 'rgba(0,0,0,0.04)' }} />
        <Bar dataKey="count" name="Reports" fill={SERIES} radius={[4, 4, 0, 0]} maxBarSize={48} />
      </BarChart>
    </ResponsiveContainer>
  );
}

// "2026-11-02" becomes "2 Nov", read as a calendar date so no time zone
// can move it to the day before.
function weekLabel(weekStart: string): string {
  const [year = 1970, month = 1, day = 1] = weekStart.split('-').map(Number);
  const date = new Date(Date.UTC(year, month - 1, day));
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' });
}

export function SeverityChart({ data }: { data: NamedCount[] }) {
  return (
    <ChartCard
      title="Reports by severity"
      description="The current severity of each of your reports, including any you changed."
      rows={data.map((row) => ({ label: row.name, count: row.count }))}
      firstColumn="Severity"
    >
      <CountBars data={data} />
    </ChartCard>
  );
}

export function CategoryChart({ data }: { data: NamedCount[] }) {
  return (
    <ChartCard
      title="Reports by category"
      description="The current category of each of your reports."
      rows={data.map((row) => ({ label: row.name, count: row.count }))}
      firstColumn="Category"
    >
      <CountBars data={data} />
    </ChartCard>
  );
}

export function WeeklyChart({ data }: { data: WeekCount[] }) {
  const rows = data.map((row) => ({ label: weekLabel(row.week_start), count: row.count }));
  return (
    <ChartCard
      title="Reports per week"
      description="Reports you created, by the week starting on Monday."
      rows={rows.map((row) => ({ label: `Week of ${row.label}`, count: row.count }))}
      firstColumn="Week"
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -16 }}>
          <CartesianGrid vertical={false} stroke={GRID} />
          <XAxis dataKey="label" tick={TICK} tickLine={false} axisLine={{ stroke: GRID }} />
          <YAxis allowDecimals={false} tick={TICK} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ stroke: AXIS, strokeDasharray: '3 3' }} />
          <Line
            type="monotone"
            dataKey="count"
            name="Reports"
            stroke={SERIES}
            strokeWidth={2}
            dot={{ r: 4, fill: SERIES, stroke: '#ffffff', strokeWidth: 2 }}
            activeDot={{ r: 5 }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartCard>
  );
}
