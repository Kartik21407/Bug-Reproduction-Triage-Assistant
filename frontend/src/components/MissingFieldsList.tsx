// The fields the user's analysed reports most often leave out, as a ranked
// list with counts (US-30 criterion 1). Each row's bar is the share of
// analysed reports missing that field.

import type { MissingFieldsRead } from '@/types/api';

interface MissingFieldsListProps {
  data: MissingFieldsRead;
  limit?: number;
}

export function MissingFieldsList({ data, limit }: MissingFieldsListProps) {
  const missing = data.fields.filter((field) => field.count > 0).slice(0, limit);
  if (data.analysed_reports === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Once a report has been analysed, the details you most often leave out show up here.
      </p>
    );
  }
  if (missing.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Nothing is missing from your analysed reports. Nice work.
      </p>
    );
  }
  return (
    <ol aria-label="Most commonly missing fields" className="flex flex-col gap-3">
      {missing.map((field, index) => {
        const share = Math.round((field.count / data.analysed_reports) * 100);
        return (
          <li key={field.field} className="flex flex-col gap-1">
            <div className="flex justify-between gap-3 text-sm">
              <span className="font-medium">
                <span className="mr-2 text-muted-foreground tabular-nums">{index + 1}.</span>
                {field.name}
              </span>
              <span className="tabular-nums text-muted-foreground">
                {field.count} of {data.analysed_reports}
              </span>
            </div>
            <div className="h-2 rounded-full bg-muted" aria-hidden="true">
              <div className="h-2 rounded-full bg-primary" style={{ width: `${share}%` }} />
            </div>
          </li>
        );
      })}
    </ol>
  );
}
