// Shared Loading, Empty and Error presentations. Pages use these instead of
// writing their own spinner or error box, so every screen looks the same in
// these states.

interface EmptyStateProps {
  title: string;
  description?: string;
  action?: React.ReactNode;
}

interface ErrorStateProps {
  message: string;
}

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div
      role="status"
      className="flex items-center justify-center p-8 text-sm text-muted-foreground"
    >
      {label}
    </div>
  );
}

export function EmptyState({ title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed p-8 text-center">
      <p className="font-medium">{title}</p>
      {description && <p className="text-sm text-muted-foreground">{description}</p>}
      {action}
    </div>
  );
}

export function ErrorState({ message }: ErrorStateProps) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-destructive/50 p-4 text-sm text-destructive"
    >
      {message}
    </div>
  );
}
