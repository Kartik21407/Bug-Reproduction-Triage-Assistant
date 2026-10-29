// A small pill showing one of the four verification labels (FR-27). Colour
// is the only thing that varies; the text is always the label's own name,
// never abbreviated, so a screen reader announces exactly what is shown.

import type { Label } from '@/types/api';

const LABEL_STYLES: Record<Label, string> = {
  Explicit: 'bg-green-100 text-green-800',
  Inferred: 'bg-amber-100 text-amber-800',
  Unverified: 'bg-orange-100 text-orange-800',
  Missing: 'bg-muted text-muted-foreground',
};

export function LabelBadge({ label }: { label: Label }) {
  return (
    <span
      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${LABEL_STYLES[label]}`}
    >
      {label}
    </span>
  );
}
