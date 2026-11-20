// The editing form for one section of the generated report (US-24
// criterion 1), shaped to what the section holds: text for a single value,
// one item per line for steps and error messages, "name: value" lines for
// the environment, a dropdown for a triage value, and frequency plus a note
// for Additional Information. Saving is the page's job; this only collects.

import { useState } from 'react';
import type {
  EditableValues,
  ReportEditRequest,
  ReportSection,
  TriageField,
  TriageRead,
} from '@/types/api';

const TRIAGE_KEYS: TriageField[] = ['severity', 'priority', 'category', 'reproducibility'];

type SingleField = 'title' | 'summary' | 'expected_behaviour' | 'actual_behaviour';

interface ReportSectionEditorProps {
  section: ReportSection;
  values: EditableValues;
  triage: TriageRead | undefined;
  isSaving: boolean;
  onSave: (edits: ReportEditRequest[]) => void;
  onTriageSave: (field: TriageField, value: string) => void;
  onCancel: () => void;
}

function parseEnvironment(text: string): { name: string; value: string }[] | null {
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  const parsed = lines.map((line) => {
    const colon = line.indexOf(':');
    if (colon <= 0) return null;
    return { name: line.slice(0, colon).trim(), value: line.slice(colon + 1).trim() };
  });
  if (parsed.some((entry) => entry === null || !entry.value)) return null;
  return parsed as { name: string; value: string }[];
}

export function ReportSectionEditor({
  section,
  values,
  triage,
  isSaving,
  onSave,
  onTriageSave,
  onCancel,
}: ReportSectionEditorProps) {
  const field = section.fields[0];
  const isTriage = TRIAGE_KEYS.includes(field as TriageField);
  const listField = field === 'steps' || field === 'error_messages' ? field : null;

  const [text, setText] = useState(() => {
    if (listField) return values[listField].join('\n');
    if (field === 'environment')
      return values.environment.map((d) => `${d.name}: ${d.value}`).join('\n');
    if (field === 'frequency') return values.frequency ?? '';
    if (isTriage) return triage?.[field as TriageField].value ?? '';
    return values[field as SingleField] ?? '';
  });
  const [note, setNote] = useState(values.additional_information ?? '');
  const [error, setError] = useState<string | null>(null);

  const inputId = `edit-${section.key}`;

  const save = () => {
    setError(null);
    if (isTriage) {
      onTriageSave(field as TriageField, text);
      return;
    }
    if (listField) {
      onSave([{ field: listField, items: text.split('\n').map((line) => line.trim()) }]);
      return;
    }
    if (field === 'environment') {
      const environment = parseEnvironment(text);
      if (environment === null) {
        setError('Write each detail on its own line as name: value, for example browser: Chrome');
        return;
      }
      onSave([{ field: 'environment', environment }]);
      return;
    }
    if (field === 'frequency') {
      onSave([
        { field: 'frequency', text },
        { field: 'additional_information', text: note },
      ]);
      return;
    }
    onSave([{ field: field as SingleField, text }]);
  };

  return (
    <div className="flex flex-col gap-2">
      {isTriage ? (
        <>
          <label htmlFor={inputId} className="text-xs font-medium">
            {section.heading}
          </label>
          <select
            id={inputId}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="rounded-md border px-3 py-2 text-sm"
          >
            {triage?.[field as TriageField].options.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </>
      ) : field === 'frequency' ? (
        <>
          <label htmlFor={inputId} className="text-xs font-medium">
            Frequency
          </label>
          <input
            id={inputId}
            value={text}
            onChange={(event) => setText(event.target.value)}
            className="rounded-md border px-3 py-2 text-sm"
          />
          <label htmlFor={`${inputId}-note`} className="text-xs font-medium">
            Anything else a developer should know
          </label>
          <textarea
            id={`${inputId}-note`}
            value={note}
            onChange={(event) => setNote(event.target.value)}
            rows={3}
            className="rounded-md border px-3 py-2 text-sm"
          />
        </>
      ) : (
        <>
          <label htmlFor={inputId} className="text-xs font-medium">
            {listField
              ? `${section.heading}, one per line`
              : field === 'environment'
                ? 'Environment, one detail per line as name: value'
                : section.heading}
          </label>
          <textarea
            id={inputId}
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={listField || field === 'environment' ? 5 : field === 'title' ? 1 : 3}
            className="rounded-md border px-3 py-2 text-sm"
          />
        </>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="flex gap-2">
        <button
          type="button"
          onClick={save}
          disabled={isSaving}
          className="rounded-md bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground disabled:opacity-60"
        >
          {isSaving ? 'Saving…' : 'Save'}
        </button>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border px-3 py-1.5 text-xs font-medium"
        >
          Cancel
        </button>
      </div>
    </div>
  );
}
