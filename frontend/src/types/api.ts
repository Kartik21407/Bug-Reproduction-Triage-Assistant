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
