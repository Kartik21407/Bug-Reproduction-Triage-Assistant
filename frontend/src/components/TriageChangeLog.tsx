// Who changed a triage value, from what, to what, and when (US-18
// criterion 1), newest first.

import type { TriageChange } from '@/types/api';

const FIELD_NAMES: Record<TriageChange['field'], string> = {
  severity: 'Severity',
  priority: 'Priority',
  category: 'Category',
  reproducibility: 'Reproducibility',
};

export function TriageChangeLog({ changes }: { changes: TriageChange[] }) {
  if (changes.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No one has changed a suggested value yet. Every change made here is recorded.
      </p>
    );
  }
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <caption className="sr-only">Triage change log</caption>
        <thead>
          <tr className="border-b text-xs uppercase tracking-wide text-muted-foreground">
            <th scope="col" className="py-2 pr-4 font-semibold">
              When
            </th>
            <th scope="col" className="py-2 pr-4 font-semibold">
              Who
            </th>
            <th scope="col" className="py-2 pr-4 font-semibold">
              Field
            </th>
            <th scope="col" className="py-2 font-semibold">
              Change
            </th>
          </tr>
        </thead>
        <tbody>
          {changes.map((change) => (
            <tr key={`${change.changed_at}-${change.field}`} className="border-b last:border-b-0">
              <td className="whitespace-nowrap py-2 pr-4 text-muted-foreground">
                {new Date(change.changed_at).toLocaleString(undefined, {
                  dateStyle: 'medium',
                  timeStyle: 'short',
                })}
              </td>
              <td className="py-2 pr-4">{change.changed_by}</td>
              <td className="py-2 pr-4">{FIELD_NAMES[change.field]}</td>
              <td className="py-2">
                <span className="text-muted-foreground line-through">{change.old_value}</span>
                {' to '}
                <span className="font-medium">{change.new_value}</span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
