// The most similar existing issues for one report, most similar first
// (US-20 criterion 1), each with its score and a Likely or Possible label
// (criterion 2). The wording never says a report is a duplicate; only a
// person can decide that (criterion 3, DR-05), with the "Duplicate" and
// "Not duplicate" buttons on each candidate (US-21 criterion 1).

import { Link } from 'react-router-dom';
import type { DuplicateCandidate, DuplicateDecision, DuplicateLabel } from '@/types/api';

const LABEL_STYLES: Record<DuplicateLabel, string> = {
  'Likely duplicate': 'bg-amber-100 text-amber-800',
  'Possible duplicate': 'bg-muted text-muted-foreground',
};

const DECISION_BUTTONS: { decision: DuplicateDecision; text: string }[] = [
  { decision: 'duplicate', text: 'Duplicate' },
  { decision: 'not_duplicate', text: 'Not duplicate' },
];

interface DuplicateCandidateListProps {
  candidates: DuplicateCandidate[];
  comparedCount: number;
  isDeciding: boolean;
  onDecide: (candidateId: string, decision: DuplicateDecision | null) => void;
}

function CandidateLink({ candidate }: { candidate: DuplicateCandidate }) {
  if (candidate.source === 'report') {
    return (
      <Link to={candidate.url} className="text-sm font-medium underline">
        {candidate.title}
      </Link>
    );
  }
  return (
    <a
      href={candidate.url}
      target="_blank"
      rel="noreferrer"
      className="text-sm font-medium underline"
    >
      {candidate.title}
    </a>
  );
}

export function DuplicateCandidateList({
  candidates,
  comparedCount,
  isDeciding,
  onDecide,
}: DuplicateCandidateListProps) {
  if (comparedCount === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        There are no existing issues to compare against yet.
      </p>
    );
  }

  if (candidates.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No similar issues found among the {comparedCount} compared.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-2">
      <ol aria-label="Similar existing issues" className="flex flex-col gap-2">
        {candidates.map((candidate) => (
          <li
            key={`${candidate.source}-${candidate.id}`}
            className="flex flex-col gap-3 rounded-md border p-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="flex flex-col gap-1">
              <CandidateLink candidate={candidate} />
              <span className="text-xs text-muted-foreground">
                {candidate.source === 'report' ? 'One of your earlier reports' : 'Existing issue'}
                {' · '}
                Similarity {candidate.score.toFixed(2)}
              </span>
            </div>
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <span
                className={`rounded-full px-2 py-0.5 text-xs font-medium ${LABEL_STYLES[candidate.label]}`}
              >
                {candidate.label}
              </span>
              {DECISION_BUTTONS.map(({ decision, text }) => {
                const chosen = candidate.decision === decision;
                return (
                  <button
                    key={decision}
                    type="button"
                    aria-pressed={chosen}
                    aria-label={`${text}: ${candidate.title}`}
                    disabled={isDeciding}
                    onClick={() => onDecide(candidate.candidate_id, chosen ? null : decision)}
                    className={`rounded-md border px-2 py-1 text-xs font-medium disabled:opacity-60 ${
                      chosen ? 'bg-primary text-primary-foreground' : ''
                    }`}
                  >
                    {text}
                  </button>
                );
              })}
            </div>
          </li>
        ))}
      </ol>
      <p className="text-xs text-muted-foreground">
        A similarity score is supporting evidence, not a decision. Only a person can confirm a
        duplicate; click a chosen button again to take it back.
      </p>
    </div>
  );
}
