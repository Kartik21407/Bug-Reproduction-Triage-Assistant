// Single report view with editing and delete-with-confirmation (US-07).

import { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useNavigate, useParams } from 'react-router-dom';
import { useDeleteReport, useReport, useUpdateReport } from '@/hooks/useReports';
import { ApiRequestError } from '@/lib/api';
import { ErrorState, LoadingState } from '@/components/states';
import { ReportInput } from '@/components/ReportInput';
import { reportInputSchema, type ReportInputValues } from '@/lib/reportInputSchema';

function formatDateTime(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function ReportDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [isEditing, setIsEditing] = useState(false);

  const { data: report, isLoading, error } = useReport(id ?? '');
  const updateReport = useUpdateReport(id ?? '');
  const deleteReport = useDeleteReport();

  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<ReportInputValues>({ resolver: zodResolver(reportInputSchema) });

  // Fills the edit form from the loaded report. Runs again whenever the
  // report data changes, including right after a successful save.
  useEffect(() => {
    if (report) {
      reset({ original_text: report.original_text, logs: report.logs ?? '' });
    }
  }, [report, reset]);

  const textValue = watch('original_text');
  const logsValue = watch('logs');

  const onSubmit = handleSubmit((values) => {
    updateReport.mutate(
      { original_text: values.original_text, logs: values.logs || undefined },
      { onSuccess: () => setIsEditing(false) },
    );
  });

  // US-07 criterion 2: deletion asks for confirmation.
  const handleDelete = () => {
    if (!id) return;
    if (window.confirm('Delete this report? This cannot be undone.')) {
      deleteReport.mutate(id, { onSuccess: () => navigate('/reports', { replace: true }) });
    }
  };

  if (isLoading) {
    return <LoadingState label="Loading report…" />;
  }

  if (error instanceof ApiRequestError && error.status === 404) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorState message="Report not found." />
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <ErrorState message="Could not load this report. Try again." />
      </div>
    );
  }

  const updateError =
    updateReport.error instanceof ApiRequestError
      ? updateReport.error.message
      : updateReport.error
        ? 'Something went wrong. Try again.'
        : null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-semibold">{report.title ?? 'Untitled report'}</h1>
        <div className="flex gap-3">
          {!isEditing && (
            <button
              type="button"
              onClick={() => setIsEditing(true)}
              className="rounded-md border px-3 py-2 text-sm font-medium"
            >
              Edit
            </button>
          )}
          <button
            type="button"
            onClick={handleDelete}
            disabled={deleteReport.isPending}
            className="rounded-md border border-destructive px-3 py-2 text-sm font-medium text-destructive disabled:opacity-60"
          >
            Delete
          </button>
        </div>
      </div>

      <p className="text-xs text-muted-foreground">
        {report.severity ?? 'Not yet triaged'} · {report.state} · Submitted{' '}
        {formatDateTime(report.created_at)}
      </p>

      {isEditing ? (
        <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
          {updateError && <ErrorState message={updateError} />}
          <ReportInput
            register={register}
            errors={errors}
            textValue={textValue}
            logsValue={logsValue}
          />
          <div className="flex gap-3">
            <button
              type="submit"
              disabled={updateReport.isPending}
              className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
            >
              {updateReport.isPending ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              onClick={() => {
                reset({ original_text: report.original_text, logs: report.logs ?? '' });
                setIsEditing(false);
              }}
              className="rounded-md border px-3 py-2 text-sm font-medium"
            >
              Cancel
            </button>
          </div>
        </form>
      ) : (
        <div className="flex flex-col gap-4">
          <div className="flex flex-col gap-1">
            <span className="text-sm font-medium">Bug description</span>
            <p className="whitespace-pre-wrap rounded-md border p-3 text-sm">
              {report.original_text}
            </p>
          </div>

          {report.logs && (
            <div className="flex flex-col gap-1">
              <span className="text-sm font-medium">Logs</span>
              <pre className="overflow-x-auto whitespace-pre-wrap rounded-md border p-3 font-mono text-xs">
                {report.logs}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
