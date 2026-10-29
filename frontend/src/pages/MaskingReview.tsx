// Masking review (US-32): previews what would be masked, lets the user
// restore a false positive or mask something by hand, then runs analysis
// with those adjustments. Only the masked copy is ever sent anywhere; the
// original stays visible to the owner on ReportDetail (criterion 5).

import { useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useMaskPreview, useAnalyzeReport } from '@/hooks/useAnalysis';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';
import { MaskedItemList } from '@/components/MaskedItemList';

export default function MaskingReview() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const reportId = id ?? '';

  const [restoredValues, setRestoredValues] = useState<string[]>([]);
  const [manualValues, setManualValues] = useState<string[]>([]);

  const { data: preview, isLoading, error } = useMaskPreview(reportId);
  const analyzeReport = useAnalyzeReport(reportId);

  if (isLoading) {
    return <LoadingState label="Checking for secrets…" />;
  }

  if (error instanceof ApiRequestError && error.status === 404) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorState message="Report not found." />
      </div>
    );
  }

  if (error || !preview) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorState message="Could not check this report for secrets. Try again." />
      </div>
    );
  }

  const analyzeError =
    analyzeReport.error instanceof ApiRequestError
      ? analyzeReport.error.message
      : analyzeReport.error
        ? 'Something went wrong. Try again.'
        : null;

  const handleRunAnalysis = () => {
    analyzeReport.mutate(
      { restore_values: restoredValues, manual_mask_values: manualValues },
      { onSuccess: () => navigate(`/reports/${reportId}/analysis`) },
    );
  };

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">Review before analysis</h1>
        <p className="text-sm text-muted-foreground">
          This is what would be sent for analysis. Only the masked copy ever leaves the system; your
          original text stays visible to you.
        </p>
      </div>

      {analyzeError && <ErrorState message={analyzeError} />}

      <MaskedItemList
        items={preview.items}
        restoredValues={restoredValues}
        manualValues={manualValues}
        onRestore={(value) => setRestoredValues((current) => [...current, value])}
        onUnrestore={(value) => setRestoredValues((current) => current.filter((v) => v !== value))}
        onAddManual={(value) => setManualValues((current) => [...current, value])}
        onRemoveManual={(value) => setManualValues((current) => current.filter((v) => v !== value))}
      />

      <div className="flex flex-col gap-1">
        <span className="text-sm font-medium">Masked preview</span>
        <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border p-3 font-mono text-xs">
          {preview.masked_text}
        </pre>
      </div>

      <button
        type="button"
        onClick={handleRunAnalysis}
        disabled={analyzeReport.isPending}
        className="self-start rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
      >
        {analyzeReport.isPending ? 'Analysing…' : 'Run analysis'}
      </button>
    </div>
  );
}
