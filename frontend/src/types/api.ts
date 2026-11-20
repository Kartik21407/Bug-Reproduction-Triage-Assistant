// TypeScript mirrors of the backend request and response shapes in
// backend/app/schemas/. Kept in step with those files: when one changes,
// the other changes in the same pull request.

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
  // Fields a person has their own version of; re-analysis keeps them.
  corrected_fields: string[];
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

// --- Triage (Sprint 3: US-15, US-16, US-17) ---------------------------------
// Mirrors backend/app/schemas/triage.py.

export type TriageField = 'severity' | 'priority' | 'category' | 'reproducibility';

export interface TriageValue {
  value: string;
  suggested_value: string;
  reason: string;
  overridden: boolean;
  options: string[];
}

export type TriageRead = Record<TriageField, TriageValue>;

export interface TriageOverrideRequest {
  field: TriageField;
  value: string;
}

// --- Duplicates (Sprint 3: US-20) --------------------------------------------
// Mirrors backend/app/schemas/duplicates.py.

export type DuplicateLabel = 'Likely duplicate' | 'Possible duplicate';

export type DuplicateDecision = 'duplicate' | 'not_duplicate';

export interface DuplicateCandidate {
  id: string;
  // This candidate row's id, the one a decision is posted against.
  candidate_id: string;
  source: 'corpus' | 'report';
  title: string;
  url: string;
  score: number;
  label: DuplicateLabel;
  rank: number;
  decision: DuplicateDecision | null;
}

export interface DuplicatesRead {
  searched: boolean;
  compared_count: number;
  candidates: DuplicateCandidate[];
}

// --- Generated report (Sprint 3: US-23) ---------------------------------------
// Mirrors backend/app/report/template.py.

export interface ReportLine {
  text: string;
  label: Label | null;
  note: string | null;
  url: string | null;
  preformatted: boolean;
}

export interface ReportSection {
  key: string;
  heading: string;
  provided: boolean;
  lines: ReportLine[];
  // The fields this section is built from and edited through (US-24).
  fields: string[];
  // A person's own version is in force, so it can be reset.
  edited: boolean;
}

export interface EnvironmentValue {
  name: string;
  value: string;
}

export interface EditableValues {
  title: string | null;
  summary: string | null;
  expected_behaviour: string | null;
  actual_behaviour: string | null;
  frequency: string | null;
  additional_information: string | null;
  steps: string[];
  error_messages: string[];
  environment: EnvironmentValue[];
}

export interface GeneratedReport {
  sections: ReportSection[];
  values: EditableValues;
}

// --- Report editing and export (Sprint 4: US-24, US-25) ----------------------
// Mirrors backend/app/schemas/report.py.

export type EditableField =
  | 'title'
  | 'summary'
  | 'expected_behaviour'
  | 'actual_behaviour'
  | 'frequency'
  | 'steps'
  | 'error_messages'
  | 'environment'
  | 'additional_information';

export interface ReportEditRequest {
  field: EditableField;
  text?: string | null;
  items?: string[];
  environment?: EnvironmentValue[];
}

export interface MarkdownRead {
  markdown: string;
  warnings: string[];
}

// --- GitHub (Sprint 4: US-26, US-27) -----------------------------------------
// Mirrors backend/app/schemas/github.py. No shape here can carry the token.

export interface GitHubConnection {
  connected: boolean;
  login: string | null;
  repository: string | null;
}

export interface GitHubRepository {
  full_name: string;
  private: boolean;
}

export interface LikelyDuplicate {
  title: string;
  url: string;
  score: number;
}

export interface IssuePreview {
  repository: string | null;
  title: string;
  body: string;
  labels: string[];
  likely_duplicates: LikelyDuplicate[];
  warnings: string[];
  issue_url: string | null;
}

export interface IssueCreated {
  issue_url: string;
  issue_number: number | null;
  created: boolean;
}

// --- Analytics (Sprint 4: US-29) ---------------------------------------------
// Mirrors backend/app/schemas/analytics.py.

export interface NamedCount {
  name: string;
  count: number;
}

export interface WeekCount {
  week_start: string;
  count: number;
}

export interface AnalyticsRead {
  total_reports: number;
  by_severity: NamedCount[];
  by_category: NamedCount[];
  by_week: WeekCount[];
}
