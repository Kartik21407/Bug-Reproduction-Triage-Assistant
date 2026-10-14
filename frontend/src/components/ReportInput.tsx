// The report text area with its optional log field, character counters and
// inline validation (US-04, US-05). Used by NewReport (create) and
// ReportDetail's edit mode (US-07), which is why it lives here rather than
// inside either page. Validation itself lives in lib/reportInputSchema.ts.

import type { FieldErrors, UseFormRegister } from 'react-hook-form';
import { MAX_LOGS_LENGTH, MAX_TEXT_LENGTH, type ReportInputValues } from '@/lib/reportInputSchema';

interface ReportInputProps {
  register: UseFormRegister<ReportInputValues>;
  errors: FieldErrors<ReportInputValues>;
  textValue: string;
  logsValue: string;
}

export function ReportInput({ register, errors, textValue, logsValue }: ReportInputProps) {
  return (
    <>
      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <label htmlFor="original_text" className="text-sm font-medium">
            Bug description
          </label>
          <span className="text-xs text-muted-foreground">
            {textValue?.length ?? 0} / {MAX_TEXT_LENGTH.toLocaleString()}
          </span>
        </div>
        <textarea
          id="original_text"
          rows={8}
          aria-invalid={Boolean(errors.original_text)}
          aria-describedby={errors.original_text ? 'original_text-error' : undefined}
          className="rounded-md border px-3 py-2 text-sm"
          {...register('original_text')}
        />
        {errors.original_text && (
          <p id="original_text-error" className="text-sm text-destructive">
            {errors.original_text.message}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <label htmlFor="logs" className="text-sm font-medium">
            Logs <span className="font-normal text-muted-foreground">(optional)</span>
          </label>
          <span className="text-xs text-muted-foreground">
            {logsValue?.length ?? 0} / {MAX_LOGS_LENGTH.toLocaleString()}
          </span>
        </div>
        {/* Monospace, unmodified (US-05 criterion 2). */}
        <textarea
          id="logs"
          rows={6}
          aria-invalid={Boolean(errors.logs)}
          aria-describedby={errors.logs ? 'logs-error' : undefined}
          className="rounded-md border px-3 py-2 font-mono text-xs"
          {...register('logs')}
        />
        {errors.logs && (
          <p id="logs-error" className="text-sm text-destructive">
            {errors.logs.message}
          </p>
        )}
      </div>
    </>
  );
}
