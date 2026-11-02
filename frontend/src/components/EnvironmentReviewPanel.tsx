// Captured environment details, each correctable or removable in place
// (US-33 criterion 1), plus the one open question about anything else
// relevant (criterion 2), or what the reporter was using when nothing was
// captured at all (criterion 3).

import { useState } from 'react';
import { LabelBadge } from '@/components/LabelBadge';
import type { EnvironmentDetail } from '@/types/api';

interface EnvironmentReviewPanelProps {
  details: EnvironmentDetail[];
  onCorrect: (name: string, value: string) => void;
  onRemove: (name: string) => void;
  onSubmitAdditionalDetails: (text: string) => void;
  isSubmitting: boolean;
}

function DetailRow({
  detail,
  onCorrect,
  onRemove,
}: {
  detail: EnvironmentDetail;
  onCorrect: (name: string, value: string) => void;
  onRemove: (name: string) => void;
}) {
  const [isEditing, setIsEditing] = useState(false);
  const [value, setValue] = useState(detail.value);

  if (isEditing) {
    return (
      <li className="flex items-center gap-2 rounded-md border p-2">
        <span className="text-sm font-medium">{detail.name}</span>
        <input
          type="text"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="flex-1 rounded-md border px-2 py-1 text-sm"
          aria-label={`Value for ${detail.name}`}
        />
        <button
          type="button"
          onClick={() => {
            onCorrect(detail.name, value);
            setIsEditing(false);
          }}
          className="shrink-0 rounded-md border px-2 py-1 text-xs font-medium"
        >
          Save
        </button>
      </li>
    );
  }

  return (
    <li className="flex items-center justify-between gap-2 rounded-md border p-2">
      <div className="flex items-center gap-2">
        <span className="text-sm font-medium">{detail.name}</span>
        <span className="text-sm">{detail.value}</span>
        <LabelBadge label={detail.label} />
      </div>
      <div className="flex shrink-0 gap-2">
        <button
          type="button"
          onClick={() => setIsEditing(true)}
          className="rounded-md border px-2 py-1 text-xs font-medium"
        >
          Correct
        </button>
        <button
          type="button"
          onClick={() => onRemove(detail.name)}
          className="rounded-md border px-2 py-1 text-xs font-medium"
        >
          Remove
        </button>
      </div>
    </li>
  );
}

export function EnvironmentReviewPanel({
  details,
  onCorrect,
  onRemove,
  onSubmitAdditionalDetails,
  isSubmitting,
}: EnvironmentReviewPanelProps) {
  const [additional, setAdditional] = useState('');

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!additional.trim()) return;
    onSubmitAdditionalDetails(additional.trim());
    setAdditional('');
  };

  // US-33 criterion 3: a specific prompt when nothing was extracted at all.
  const prompt =
    details.length === 0
      ? 'What device, browser or operating system were you using?'
      : 'Is there anything else about the setup, account, data or timing that matters?';

  return (
    <div className="flex flex-col gap-4">
      {details.length > 0 && (
        <ul className="flex flex-col gap-2">
          {details.map((detail) => (
            <DetailRow
              key={detail.name}
              detail={detail}
              onCorrect={onCorrect}
              onRemove={onRemove}
            />
          ))}
        </ul>
      )}

      <form onSubmit={handleSubmit} className="flex flex-col gap-2">
        <label htmlFor="additional-environment-details" className="text-sm font-medium">
          {prompt}
        </label>
        <textarea
          id="additional-environment-details"
          rows={2}
          value={additional}
          onChange={(event) => setAdditional(event.target.value)}
          className="rounded-md border px-3 py-2 text-sm"
        />
        <button
          type="submit"
          disabled={isSubmitting || !additional.trim()}
          className="self-start rounded-md border px-3 py-1.5 text-xs font-medium disabled:opacity-60"
        >
          Add
        </button>
      </form>
    </div>
  );
}
