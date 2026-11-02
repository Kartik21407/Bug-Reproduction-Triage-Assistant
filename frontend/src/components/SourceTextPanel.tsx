// Shows the original report text, highlighting the currently selected
// field's source quote (US-12 criterion 1). A case-insensitive, first-match
// highlight is enough here: it answers "where did this come from", not a
// full diffing tool.

interface SourceTextPanelProps {
  text: string;
  highlight: string | null;
}

export function SourceTextPanel({ text, highlight }: SourceTextPanelProps) {
  if (!highlight) {
    return <p className="whitespace-pre-wrap rounded-md border p-3 text-sm">{text}</p>;
  }

  const index = text.toLowerCase().indexOf(highlight.toLowerCase());
  if (index === -1) {
    return <p className="whitespace-pre-wrap rounded-md border p-3 text-sm">{text}</p>;
  }

  const before = text.slice(0, index);
  const match = text.slice(index, index + highlight.length);
  const after = text.slice(index + highlight.length);

  return (
    <p className="whitespace-pre-wrap rounded-md border p-3 text-sm">
      {before}
      <mark className="rounded bg-yellow-200 px-0.5">{match}</mark>
      {after}
    </p>
  );
}
