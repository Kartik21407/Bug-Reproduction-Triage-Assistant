// TypeScript mirrors of the backend request and response shapes in
// backend/app/schemas/core.py. Kept in step with that file: when one
// changes, the other changes in the same pull request.

// --- Auth (US-01) ----------------------------------------------------------

export interface UserCreate {
  email: string;
  password: string;
}

export interface UserLogin {
  email: string;
  password: string;
}

export interface UserRead {
  id: string;
  email: string;
  created_at: string;
}

export interface ApiError {
  detail: string | { msg: string; loc: (string | number)[] }[];
}

// --- Reports (US-02, US-04, US-05, US-06, US-07) ----------------------------

export type ReportState = 'Draft' | 'Analysed' | 'Reviewed' | 'Exported' | 'Submitted';
export type Severity = 'Critical' | 'High' | 'Medium' | 'Low';

export interface ReportCreate {
  original_text: string;
  logs?: string;
}

export interface ReportRead {
  id: string;
  title: string | null;
  original_text: string;
  logs: string | null;
  state: ReportState;
  severity: Severity | null;
  created_at: string;
  updated_at: string;
}

export interface ReportListResponse {
  items: ReportRead[];
  total: number;
}

export interface ReportUpdate {
  original_text?: string;
  logs?: string;
}

// --- Analysis (Sprint 2: US-08 to US-14, US-32, US-33) ----------------------
// Mirrors backend/app/analysis/schema.py, masking.py, questions.py,
// completeness.py and backend/app/schemas/analysis.py.

export type Label = 'Explicit' | 'Inferred' | 'Unverified' | 'Missing';

export interface ExtractedField {
  value: string | null;
  source_quote: string | null;
  label: Label;
  confidence: number | null;
  reason: string | null;
}

export interface EnvironmentDetail {
  name: string;
  value: string;
  source_quote: string;
  label: Label;
}

export interface ExtractionResult {
  title: ExtractedField;
  summary: ExtractedField;
  expected_behaviour: ExtractedField;
  actual_behaviour: ExtractedField;
  frequency: ExtractedField;
  steps: ExtractedField[];
  environment: EnvironmentDetail[];
  error_messages: ExtractedField[];
}

// Mirrors backend/app/schemas/analysis.py PersistedQuestion: a follow-up
// question as read back after persistence, which is the only shape the
// frontend ever sees (both analyze and the read-back endpoint return
// questions this way, so an answer can be posted against `id`).
export interface FollowUpQuestion {
  id: string;
  field: string;
  question: string;
  reason: string;
  model_proposed: boolean;
  answer: string | null;
  answered_at: string | null;
}

export type MaskedItemType = 'email' | 'password' | 'api_key' | 'token' | 'manual';

export interface MaskedItem {
  type: MaskedItemType;
  original_text: string;
  start: number;
  end: number;
}

export interface MaskingResult {
  masked_text: string;
  items: MaskedItem[];
}

export interface CompletenessScore {
  verified_count: number;
  total: number;
  missing_fields: string[];
  needs_confirmation_fields: string[];
}

export interface AnalyzeResult {
  masked_items: MaskedItem[];
  extraction: ExtractionResult;
  questions: FollowUpQuestion[];
  steps_flagged_for_review: boolean;
}

export interface AnalysisRead {
  extraction: ExtractionResult;
  questions: FollowUpQuestion[];
  completeness: CompletenessScore;
  steps_flagged_for_review: boolean;
}

export interface AnalyzeRequest {
  restore_values?: string[];
  manual_mask_values?: string[];
}

export interface AnswerQuestionRequest {
  answer: string;
}

export interface EnvironmentCorrection {
  name: string;
  value: string;
}

export interface EnvironmentReviewRequest {
  corrections?: EnvironmentCorrection[];
  removals?: string[];
  additional_details?: string;
}

// Field names an ExtractionResult carries, used to look up a field's label
// generically (for example from a FollowUpQuestion's `field`). Matches
// backend/app/api/analysis.py's _SCALAR_FIELDS plus the three list fields.
export const SCALAR_FIELD_NAMES = [
  'title',
  'summary',
  'expected_behaviour',
  'actual_behaviour',
  'frequency',
] as const;

export const FIELD_LABELS: Record<string, string> = {
  title: 'Title',
  summary: 'Summary',
  expected_behaviour: 'Expected behaviour',
  actual_behaviour: 'Actual behaviour',
  frequency: 'Frequency',
  steps: 'Reproduction steps',
  environment: 'Environment',
  error_messages: 'Error messages',
};
