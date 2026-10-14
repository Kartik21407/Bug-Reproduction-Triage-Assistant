// Page for submitting a new bug report with optional logs (US-04, US-05).

import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { useCreateReport } from '@/hooks/useReports';
import { ApiRequestError } from '@/lib/api';
import { ErrorState } from '@/components/states';
import { ReportInput } from '@/components/ReportInput';
import {
  emptyReportInputValues,
  reportInputSchema,
  type ReportInputValues,
} from '@/lib/reportInputSchema';

export default function NewReport() {
  const createReport = useCreateReport();
  const {
    register,
    handleSubmit,
    watch,
    reset,
    formState: { errors },
  } = useForm<ReportInputValues>({
    resolver: zodResolver(reportInputSchema),
    defaultValues: emptyReportInputValues,
  });

  const textValue = watch('original_text');
  const logsValue = watch('logs');

  const onSubmit = handleSubmit((values) => {
    createReport.mutate(
      { original_text: values.original_text, logs: values.logs || undefined },
      { onSuccess: () => reset(emptyReportInputValues) },
    );
  });

  // US-04 criterion 4: a Clear button empties the box, after confirmation.
  const handleClear = () => {
    if (window.confirm('Clear this report? Anything typed will be lost.')) {
      reset(emptyReportInputValues);
      createReport.reset();
    }
  };

  const serverError =
    createReport.error instanceof ApiRequestError
      ? createReport.error.message
      : createReport.error
        ? 'Something went wrong. Try again.'
        : null;

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6 p-6">
      <div>
        <h1 className="text-xl font-semibold">New report</h1>
        <p className="text-sm text-muted-foreground">
          Paste the bug description as you have it. Add logs separately below if you have them.
        </p>
      </div>

      {createReport.isSuccess && (
        <p role="status" className="rounded-md bg-muted p-3 text-sm">
          Report submitted.
        </p>
      )}

      {serverError && <ErrorState message={serverError} />}

      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
        <ReportInput
          register={register}
          errors={errors}
          textValue={textValue}
          logsValue={logsValue}
        />

        <div className="flex gap-3">
          <button
            type="submit"
            disabled={createReport.isPending}
            className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground disabled:opacity-60"
          >
            {createReport.isPending ? 'Submitting…' : 'Submit'}
          </button>
          <button
            type="button"
            onClick={handleClear}
            className="rounded-md border px-3 py-2 text-sm font-medium"
          >
            Clear
          </button>
        </div>
      </form>
    </div>
  );
}
