// The masking review list (US-32): detected items shown by type, each
// restorable as a false positive, plus a way to mask further text by hand.
// Shown even when nothing was detected, so a review is always available
// (US-32 criterion 4).

import { useState } from 'react';
import type { MaskedItem } from '@/types/api';

const TYPE_LABELS: Record<MaskedItem['type'], string> = {
  email: 'Email',
  password: 'Password',
  api_key: 'API key',
  token: 'Token',
  manual: 'Marked by you',
};

interface MaskedItemListProps {
  items: MaskedItem[];
  restoredValues: string[];
  manualValues: string[];
  onRestore: (originalText: string) => void;
  onUnrestore: (originalText: string) => void;
  onAddManual: (value: string) => void;
  onRemoveManual: (value: string) => void;
}

export function MaskedItemList({
  items,
  restoredValues,
  manualValues,
  onRestore,
  onUnrestore,
  onAddManual,
  onRemoveManual,
}: MaskedItemListProps) {
  const [manualInput, setManualInput] = useState('');

  const handleAddManual = (event: React.FormEvent) => {
    event.preventDefault();
    const value = manualInput.trim();
    if (!value) return;
    onAddManual(value);
    setManualInput('');
  };

  return (
    <div className="flex flex-col gap-4">
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          Nothing was detected automatically. You can still mask something by hand below.
        </p>
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map((item) => {
            const isRestored = restoredValues.includes(item.original_text);
            return (
              <li
                key={`${item.type}-${item.start}-${item.end}`}
                className="flex items-center justify-between gap-3 rounded-md border p-2"
              >
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-muted px-2 py-0.5 text-xs font-medium">
                    {TYPE_LABELS[item.type]}
                  </span>
                  <span
                    className={`font-mono text-xs ${isRestored ? 'line-through text-muted-foreground' : ''}`}
                  >
                    {item.original_text}
                  </span>
                </div>
                <button
                  type="button"
                  onClick={() =>
                    isRestored ? onUnrestore(item.original_text) : onRestore(item.original_text)
                  }
                  className="shrink-0 rounded-md border px-2 py-1 text-xs font-medium"
                >
                  {isRestored ? 'Mask again' : 'Not a secret'}
                </button>
              </li>
            );
          })}
        </ul>
      )}

      {manualValues.length > 0 && (
        <div className="flex flex-col gap-2">
          <span className="text-sm font-medium">Marked by you</span>
          <ul className="flex flex-col gap-2">
            {manualValues.map((value) => (
              <li
                key={value}
                className="flex items-center justify-between gap-3 rounded-md border p-2"
              >
                <span className="font-mono text-xs">{value}</span>
                <button
                  type="button"
                  onClick={() => onRemoveManual(value)}
                  className="shrink-0 rounded-md border px-2 py-1 text-xs font-medium"
                >
                  Remove
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <form onSubmit={handleAddManual} className="flex flex-col gap-2">
        <label htmlFor="manual-mask-value" className="text-sm font-medium">
          Mask something else
        </label>
        <div className="flex gap-2">
          <input
            id="manual-mask-value"
            type="text"
            value={manualInput}
            onChange={(event) => setManualInput(event.target.value)}
            placeholder="Paste the text to mask"
            className="flex-1 rounded-md border px-3 py-2 text-sm"
          />
          <button
            type="submit"
            disabled={!manualInput.trim()}
            className="shrink-0 rounded-md border px-3 py-2 text-sm font-medium disabled:opacity-60"
          >
            Mask
          </button>
        </div>
        <p className="text-xs text-muted-foreground">
          Every occurrence of this text in the report is masked too.
        </p>
      </form>
    </div>
  );
}
