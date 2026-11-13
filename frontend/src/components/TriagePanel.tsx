// The four triage values (US-15, US-16, US-17), each in an editable
// dropdown with the reason behind its suggestion (US-15 criteria 2 and 3).
// A value a person changed is marked as such, with the original suggestion
// beside it (criterion 4). Priority says plainly that it is the project
// manager's decision (US-16 criterion 2).

import type { TriageField, TriageRead } from '@/types/api';

const FIELDS: { field: TriageField; title: string }[] = [
  { field: 'severity', title: 'Severity' },
  { field: 'priority', title: 'Priority' },
  { field: 'category', title: 'Category' },
  { field: 'reproducibility', title: 'Reproducibility' },
];

interface TriagePanelProps {
  triage: TriageRead;
  isSaving: boolean;
  onChange: (field: TriageField, value: string) => void;
}

export function TriagePanel({ triage, isSaving, onChange }: TriagePanelProps) {
  return (
    <ul className="grid gap-3 sm:grid-cols-2">
      {FIELDS.map(({ field, title }) => {
        const entry = triage[field];
        const selectId = `triage-${field}`;
        return (
          <li key={field} className="flex flex-col gap-2 rounded-md border p-3">
            <div className="flex items-center justify-between gap-2">
              <label htmlFor={selectId} className="text-sm font-medium">
                {title}
              </label>
              {entry.overridden && (
                <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-medium text-blue-800">
                  Changed by you
                </span>
              )}
            </div>
            <select
              id={selectId}
              value={entry.value}
              disabled={isSaving}
              onChange={(event) => onChange(field, event.target.value)}
              className="rounded-md border px-3 py-2 text-sm disabled:opacity-60"
            >
              {entry.options.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
            {field === 'priority' && (
              <p className="text-xs font-medium text-muted-foreground">
                A suggestion only. The project manager decides priority.
              </p>
            )}
            <p className="text-xs text-muted-foreground">
              {entry.overridden ? `Suggested ${entry.suggested_value}: ` : 'Why: '}
              {entry.reason}
            </p>
          </li>
        );
      })}
    </ul>
  );
}
