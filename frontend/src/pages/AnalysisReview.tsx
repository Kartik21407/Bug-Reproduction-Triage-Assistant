// Analysis review (US-13, US-14, US-33): the extracted fields with their
// labels and source text, the completeness score, the follow-up questions,
// and environment review, all for one report.

import { useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { useAnalysisRead, useAnswerQuestion, useReviewEnvironment } from '@/hooks/useAnalysis';
import { useReport } from '@/hooks/useReports';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';
import { ExtractedFieldCard } from '@/components/ExtractedFieldCard';
import { SourceTextPanel } from '@/components/SourceTextPanel';
import { FollowUpQuestionList } from '@/components/FollowUpQuestionList';
import { EnvironmentReviewPanel } from '@/components/EnvironmentReviewPanel';

export default function AnalysisReview() {
  const { id } = useParams<{ id: string }>();
  const reportId = id ?? '';
  const [highlight, setHighlight] = useState<string | null>(null);

  const { data: report, isLoading: isReportLoading, error: reportError } = useReport(reportId);
  const {
    data: analysis,
    isLoading: isAnalysisLoading,
    error: analysisError,
  } = useAnalysisRead(reportId);
  const answerQuestion = useAnswerQuestion(reportId);
  const reviewEnvironment = useReviewEnvironment(reportId);

  if (isReportLoading || isAnalysisLoading) {
    return <LoadingState label="Loading analysis…" />;
  }

  if (reportError instanceof ApiRequestError && reportError.status === 404) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState message="Report not found." />
      </div>
    );
  }

  if (reportError || analysisError || !report || !analysis) {
    return (
      <div className="mx-auto max-w-3xl p-6">
        <ErrorState message="Could not load this report's analysis. Try again." />
      </div>
    );
  }

  const { extraction, questions, completeness, steps_flagged_for_review: stepsFlagged } = analysis;

  // Nothing has been analysed yet: no title, no summary, every essential
  // field missing. Point the user at masking review instead of showing an
  // empty results page.
  const hasAnyResult =
    report.state !== 'Draft' ||
    extraction.title.label !== 'Missing' ||
    extraction.summary.label !== 'Missing';

  if (!hasAnyResult) {
    return (
      <div className="mx-auto flex max-w-3xl flex-col gap-4 p-6">
        <h1 className="text-xl font-semibold">Analysis</h1>
        <p className="text-sm text-muted-foreground">This report has not been analysed yet.</p>
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
          <p className="text-sm text-muted-foreground">
            Completeness: {completeness.verified_count}/{completeness.total} essential fields
            verified
          </p>
        </div>
        <div className="flex shrink-0 gap-3">
          <Link
            to={`/reports/${reportId}/mask`}
            className="rounded-md border px-3 py-2 text-sm font-medium"
          >
            Re-analyse
          </Link>
          <Link
            to={`/reports/${reportId}/triage`}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground"
          >
            Continue to triage
          </Link>
        </div>
      </div>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">Original report</h2>
        <SourceTextPanel text={report.original_text} highlight={highlight} />
        {highlight && (
          <button
            type="button"
            onClick={() => setHighlight(null)}
            className="self-start text-xs font-medium underline"
          >
            Clear highlight
          </button>
        )}
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">Extracted fields</h2>
        <div className="grid gap-3 sm:grid-cols-2">
          <ExtractedFieldCard title="Title" field={extraction.title} onViewSource={setHighlight} />
          <ExtractedFieldCard
            title="Summary"
            field={extraction.summary}
            onViewSource={setHighlight}
          />
          <ExtractedFieldCard
            title="Expected behaviour"
            field={extraction.expected_behaviour}
            onViewSource={setHighlight}
          />
          <ExtractedFieldCard
            title="Actual behaviour"
            field={extraction.actual_behaviour}
            onViewSource={setHighlight}
          />
          <ExtractedFieldCard
            title="Frequency"
            field={extraction.frequency}
            onViewSource={setHighlight}
          />
        </div>

        {extraction.steps.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Reproduction steps</span>
            {stepsFlagged && (
              <p className="rounded-md border border-amber-400 bg-amber-50 p-2 text-xs text-amber-800">
                More than seven steps were extracted. Review the full list before filing; nothing
                has been shortened.
              </p>
            )}
            <ol className="flex flex-col gap-2">
              {extraction.steps.map((step, index) => (
                <li key={`${index}-${step.value}`}>
                  <ExtractedFieldCard
                    title={`Step ${index + 1}`}
                    field={step}
                    onViewSource={setHighlight}
                  />
                </li>
              ))}
            </ol>
          </div>
        )}

        {extraction.error_messages.length > 0 && (
          <div className="flex flex-col gap-2">
            <span className="text-sm font-medium">Error messages</span>
            {extraction.error_messages.map((error, index) => (
              <ExtractedFieldCard
                key={`${index}-${error.value}`}
                title={`Error ${index + 1}`}
                field={error}
                onViewSource={setHighlight}
              />
            ))}
          </div>
        )}
      </section>

      {completeness.missing_fields.length > 0 && (
        <section>
          <h2 className="text-sm font-semibold uppercase text-muted-foreground">Still missing</h2>
          <p className="text-sm text-muted-foreground">{completeness.missing_fields.join(', ')}</p>
        </section>
      )}

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">
          Follow-up questions
        </h2>
        <FollowUpQuestionList
          questions={questions}
          isSubmitting={answerQuestion.isPending}
          onAnswer={(questionId, answer) => answerQuestion.mutate({ questionId, answer })}
        />
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="text-sm font-semibold uppercase text-muted-foreground">Environment</h2>
        <EnvironmentReviewPanel
          details={extraction.environment}
          isSubmitting={reviewEnvironment.isPending}
          onCorrect={(name, value) => reviewEnvironment.mutate({ corrections: [{ name, value }] })}
          onRemove={(name) => reviewEnvironment.mutate({ removals: [name] })}
          onSubmitAdditionalDetails={(text) =>
            reviewEnvironment.mutate({ additional_details: text })
          }
        />
      </section>
    </div>
  );
}
