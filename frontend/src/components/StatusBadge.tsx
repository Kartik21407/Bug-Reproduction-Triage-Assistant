// Small coloured pills for a report's lifecycle state (DR-10) and its
// severity (US-15). The words carry the meaning; colour only helps scan.

import type { ReportState, Severity } from '@/types/api';

const STATE_STYLES: Record<ReportState, string> = {
  Draft: 'bg-muted text-muted-foreground',
  Analysed: 'bg-blue-50 text-blue-700',
  Reviewed: 'bg-violet-50 text-violet-700',
  Exported: 'bg-emerald-50 text-emerald-700',
  Submitted: 'bg-accent text-accent-foreground',
};

const SEVERITY_STYLES: Record<Severity, string> = {
  Critical: 'bg-red-50 text-red-700',
  High: 'bg-orange-50 text-orange-700',
  Medium: 'bg-amber-50 text-amber-700',
  Low: 'bg-slate-100 text-slate-600',
};

const PILL = 'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium';

export function StateBadge({ state }: { state: ReportState }) {
  return <span className={`${PILL} ${STATE_STYLES[state]}`}>{state}</span>;
}

export function SeverityBadge({ severity }: { severity: Severity | null }) {
  if (!severity) {
    return <span className={`${PILL} bg-muted text-muted-foreground`}>Not triaged</span>;
  }
  return <span className={`${PILL} ${SEVERITY_STYLES[severity]}`}>{severity}</span>;
}
