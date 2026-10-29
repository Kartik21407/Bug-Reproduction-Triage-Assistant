// One extracted field: its value (or that it is Missing), its label, and a
// way to see where it came from in the original report (US-12 criterion 1).
// Inferred fields show the reason the model gave, since that is the closest
// thing to "the rule that produced them" this project has (US-12
// criterion 2).

import { LabelBadge } from '@/components/LabelBadge';
import type { ExtractedField } from '@/types/api';

interface ExtractedFieldCardProps {
  title: string;
  field: ExtractedField;
  onViewSource?: (quote: string) => void;
}

export function ExtractedFieldCard({ title, field, onViewSource }: ExtractedFieldCardProps) {
  const isMissing = field.label === 'Missing';

  return (
    <div className="flex flex-col gap-1 rounded-md border p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{title}</span>
        <LabelBadge label={field.label} />
      </div>
      {isMissing ? (
        <p className="text-sm text-muted-foreground">Not found in this report.</p>
      ) : (
        <>
          <p className="text-sm">{field.value}</p>
          {field.source_quote && (
            <button
              type="button"
              onClick={() => onViewSource?.(field.source_quote as string)}
              className="self-start text-xs font-medium text-primary underline"
            >
              View source text
            </button>
          )}
          {field.label === 'Inferred' && field.reason && (
            <p className="text-xs text-muted-foreground">Why: {field.reason}</p>
          )}
        </>
      )}
    </div>
  );
}
