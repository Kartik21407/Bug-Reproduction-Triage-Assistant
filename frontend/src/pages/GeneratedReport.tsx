// The clean report in the standard template (US-23): every section in a
// fixed order, "Not provided" wherever there is nothing to show, and
// duplicate candidates as links. Built entirely on the server; this page
// only lays it out.

import { Link, useParams } from 'react-router-dom';
import { useReport } from '@/hooks/useReports';
import { useGeneratedReport } from '@/hooks/useGeneratedReport';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';
import { LabelBadge } from '@/components/LabelBadge';
import type { ReportLine, ReportSection } from '@/types/api';

function LineContent({ line }: { line: ReportLine }) {
  if (line.preformatted) {
    return (
      <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border p-3 font-mono text-xs">
        {line.text}
      </pre>
    );
  }
  if (line.url) {
    return line.url.startsWith('/') ? (
      <Link to={line.url} className="underline">
        {line.text}
      </Link>
    ) : (
      <a href={line.url} target="_blank" rel="noreferrer" className="underline">
        {line.text}
      </a>
    );
  }
  return <span>{line.text}</span>;
}

function Line({ line }: { line: ReportLine }) {
  return (
    <div className="flex flex-col gap-0.5">
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <LineContent line={line} />
        {/* Only a value that is not confirmed gets a badge, so an Inferred
            value is never read as fact (conflict C1). */}
        {line.label && line.label !== 'Explicit' && <LabelBadge label={line.label} />}
      </div>
      {line.note && <span className="text-xs text-muted-foreground">{line.note}</span>}
    </div>
  );
}

function Section({ section }: { section: ReportSection }) {
  return (
    <section className="flex flex-col gap-2 border-b pb-4 last:border-b-0">
      <h2 className="text-sm font-semibold">{section.heading}</h2>
      {!section.provided ? (
        <p className="text-sm italic text-muted-foreground">{section.lines[0]?.text}</p>
      ) : section.key === 'steps' ? (
        <ol className="flex list-decimal flex-col gap-1 pl-5">
          {section.lines.map((line, index) => (
            <li key={`${index}-${line.text}`}>
              <Line line={line} />
            </li>
          ))}
        </ol>
      ) : (
        <div className="flex flex-col gap-2">
          {section.lines.map((line, index) => (
            <Line key={`${index}-${line.text}`} line={line} />
          ))}
        </div>
      )}
    </section>
  );
}

export default function GeneratedReport() {
  const { id } = useParams<{ id: string }>();
  const reportId = id ?? '';

  const { data: report, isLoading: isReportLoading, error: reportError } = useReport(reportId);
  const isAnalysed = report !== undefined && report.state !== 'Draft';
  const {
    data: generated,
    isLoading: isGeneratedLoading,
    error: generatedError,
  } = useGeneratedReport(isAnalysed ? reportId : '');

  if (isReportLoading || isGeneratedLoading) {
    return <LoadingState label="Building the report…" />;
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
        <h1 className="text-xl font-semibold">Report</h1>
        <p className="text-sm text-muted-foreground">
          This report has not been analysed yet, so there is nothing to put in the template.
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

  if (generatedError || !generated) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState message="Could not build the report. Try again." />
      </div>
    );
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-xl font-semibold">Report</h1>
        <Link
          to={`/reports/${reportId}/triage`}
          className="shrink-0 rounded-md border px-3 py-2 text-sm font-medium"
        >
          Back to triage
        </Link>
      </div>
      <article className="flex flex-col gap-4 rounded-md border p-4">
        {generated.sections.map((section) => (
          <Section key={section.key} section={section} />
        ))}
      </article>
    </div>
  );
}
