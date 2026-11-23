// The clean report in the standard template (US-23), editable section by
// section with "Reset to suggested" (US-24), copied as Markdown with one
// click (US-25), marked reviewed (DR-10), and a link on to filing it on
// GitHub (US-27). Every section is built on the server; this page lays it
// out and sends edits.

import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useReport } from '@/hooks/useReports';
import {
  useEditReport,
  useGeneratedReport,
  useMarkdown,
  useMarkExported,
  useMarkReviewed,
  useResetReportField,
} from '@/hooks/useGeneratedReport';
import { useOverrideTriage, useTriage } from '@/hooks/useTriage';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';
import { LabelBadge } from '@/components/LabelBadge';
import { ReportSectionEditor } from '@/components/ReportSectionEditor';
import type {
  EditableField,
  ReportEditRequest,
  ReportLine,
  ReportSection,
  TriageField,
} from '@/types/api';

const TRIAGE_KEYS: string[] = ['severity', 'priority', 'category', 'reproducibility'];

function LineContent({ line }: { line: ReportLine }) {
  if (line.preformatted) {
    return (
      <pre className="overflow-x-auto whitespace-pre-wrap rounded-lg border bg-white p-3 font-mono text-xs">
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

function SectionBody({ section }: { section: ReportSection }) {
  if (!section.provided) {
    return <p className="text-sm italic text-muted-foreground">{section.lines[0]?.text}</p>;
  }
  if (section.key === 'steps') {
    return (
      <ol className="flex list-decimal flex-col gap-1 pl-5">
        {section.lines.map((line, index) => (
          <li key={`${index}-${line.text}`}>
            <Line line={line} />
          </li>
        ))}
      </ol>
    );
  }
  return (
    <div className="flex flex-col gap-2">
      {section.lines.map((line, index) => (
        <Line key={`${index}-${line.text}`} line={line} />
      ))}
    </div>
  );
}

export default function GeneratedReport() {
  const { id } = useParams<{ id: string }>();
  const reportId = id ?? '';
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [copyState, setCopyState] = useState<'idle' | 'copied' | 'manual'>('idle');

  const { data: report, isLoading: isReportLoading, error: reportError } = useReport(reportId);
  const isAnalysed = report !== undefined && report.state !== 'Draft';
  const {
    data: generated,
    isLoading: isGeneratedLoading,
    error: generatedError,
  } = useGeneratedReport(isAnalysed ? reportId : '');
  const { data: triage } = useTriage(reportId, { enabled: isAnalysed });
  const { data: markdown } = useMarkdown(reportId, { enabled: isAnalysed });
  const editReport = useEditReport(reportId);
  const resetField = useResetReportField(reportId);
  const overrideTriage = useOverrideTriage(reportId);
  const markExported = useMarkExported(reportId);
  const markReviewed = useMarkReviewed(reportId);

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
        <Link to={`/reports/${reportId}/mask`} className="self-start btn-primary px-3 py-2 text-sm">
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

  const saveEdits = async (edits: ReportEditRequest[]) => {
    for (const edit of edits) {
      await editReport.mutateAsync(edit);
    }
    setEditingKey(null);
  };

  const saveTriage = (field: TriageField, value: string) => {
    overrideTriage.mutate({ field, value }, { onSuccess: () => setEditingKey(null) });
  };

  const resetSection = async (section: ReportSection) => {
    if (TRIAGE_KEYS.includes(section.key) && triage) {
      const field = section.key as TriageField;
      overrideTriage.mutate({ field, value: triage[field].suggested_value });
      return;
    }
    for (const field of section.fields) {
      await resetField.mutateAsync(field as EditableField);
    }
  };

  // US-25 criterion 1: one click. The Markdown is already loaded, so the
  // copy happens straight from the click; recording the export follows.
  const copyMarkdown = async () => {
    if (!markdown) return;
    try {
      await navigator.clipboard.writeText(markdown.markdown);
      setCopyState('copied');
    } catch {
      setCopyState('manual');
    }
    markExported.mutate();
  };

  const isSaving = editReport.isPending || overrideTriage.isPending;
  const saveError = editReport.error ?? resetField.error ?? overrideTriage.error;
  const canMarkReviewed = report.state === 'Analysed';

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6 p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Report</h1>
          <p className="text-sm text-muted-foreground">Status: {report.state}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link to={`/reports/${reportId}/triage`} className="btn-secondary px-3 py-2 text-sm">
            Back to triage
          </Link>
          {canMarkReviewed && (
            <button
              type="button"
              onClick={() => markReviewed.mutate()}
              disabled={markReviewed.isPending}
              className="btn-secondary px-3 py-2 text-sm"
            >
              Mark as reviewed
            </button>
          )}
          <button
            type="button"
            onClick={copyMarkdown}
            disabled={!markdown}
            className="btn-secondary px-3 py-2 text-sm"
          >
            {copyState === 'copied' ? 'Copied' : 'Copy as Markdown'}
          </button>
          <Link to={`/reports/${reportId}/github`} className="btn-primary px-3 py-2 text-sm">
            File on GitHub
          </Link>
        </div>
      </div>

      {markdown && markdown.warnings.length > 0 && (
        <div className="rounded-xl border border-amber-400 bg-amber-50 p-3 text-sm text-amber-900">
          <p className="font-medium">Before you share this report</p>
          <ul className="list-disc pl-5">
            {markdown.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {copyState === 'manual' && markdown && (
        <div className="flex flex-col gap-1">
          <label htmlFor="markdown-copy" className="text-sm font-medium">
            Copying was blocked by the browser. Select this text and copy it instead.
          </label>
          <textarea
            id="markdown-copy"
            readOnly
            value={markdown.markdown}
            rows={10}
            className="rounded-lg border bg-white p-3 font-mono text-xs"
          />
        </div>
      )}

      {saveError && <ErrorState message="Could not save that change. Try again." />}

      <article className="flex flex-col gap-4 rounded-xl border bg-card p-4">
        {generated.sections.map((section) => (
          <section key={section.key} className="flex flex-col gap-2 border-b pb-4 last:border-b-0">
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold">{section.heading}</h2>
              {editingKey !== section.key && section.fields.length > 0 && (
                <div className="flex gap-2">
                  {section.edited && (
                    <button
                      type="button"
                      onClick={() => resetSection(section)}
                      disabled={resetField.isPending || overrideTriage.isPending}
                      aria-label={`Reset ${section.heading} to suggested`}
                      className="text-xs font-medium underline disabled:opacity-60"
                    >
                      Reset to suggested
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => setEditingKey(section.key)}
                    aria-label={`Edit ${section.heading}`}
                    className="text-xs font-medium underline"
                  >
                    Edit
                  </button>
                </div>
              )}
            </div>
            {editingKey === section.key ? (
              <ReportSectionEditor
                section={section}
                values={generated.values}
                triage={triage}
                isSaving={isSaving}
                onSave={saveEdits}
                onTriageSave={saveTriage}
                onCancel={() => setEditingKey(null)}
              />
            ) : (
              <SectionBody section={section} />
            )}
          </section>
        ))}
      </article>
    </div>
  );
}
