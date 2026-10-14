// Validation shared by the report text area and log field, used by both
// NewReport (create, US-04, US-05) and ReportDetail's edit mode (US-07).
// Kept out of components/ReportInput.tsx so that file exports only the
// component, which is what Fast Refresh needs.

import { z } from 'zod';

export const MIN_TEXT_LENGTH = 20;
export const MAX_TEXT_LENGTH = 10_000;
export const MAX_LOGS_LENGTH = 50_000;

// Mirrors backend/app/schemas/core.py ReportCreate and ReportUpdate. Length
// is checked against the trimmed text so whitespace alone cannot pass the
// minimum, matching the server (US-04 criterion 1, design.md section 8.4).
// The raw, untrimmed value is what gets submitted, so it is stored exactly
// as typed (US-04 criterion 3).
export const reportInputSchema = z.object({
  original_text: z
    .string()
    .refine(
      (v) => v.trim().length >= MIN_TEXT_LENGTH,
      `Enter at least ${MIN_TEXT_LENGTH} characters`,
    )
    .refine(
      (v) => v.trim().length <= MAX_TEXT_LENGTH,
      `Must be ${MAX_TEXT_LENGTH.toLocaleString()} characters or fewer`,
    ),
  logs: z
    .string()
    .max(MAX_LOGS_LENGTH, `Logs must be ${MAX_LOGS_LENGTH.toLocaleString()} characters or fewer`),
});

export type ReportInputValues = z.infer<typeof reportInputSchema>;

export const emptyReportInputValues: ReportInputValues = { original_text: '', logs: '' };
