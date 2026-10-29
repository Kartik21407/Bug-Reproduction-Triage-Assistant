// The filtered follow-up questions, each answerable in place (US-14). A
// question can be skipped simply by not answering it; nothing here forces
// an answer before the user moves on (US-14 criterion 6).

import { useState } from 'react';
import { FIELD_LABELS } from '@/types/api';
import type { FollowUpQuestion } from '@/types/api';

interface FollowUpQuestionListProps {
  questions: FollowUpQuestion[];
  onAnswer: (questionId: string, answer: string) => void;
  isSubmitting: boolean;
}

function QuestionRow({
  question,
  onAnswer,
  isSubmitting,
}: {
  question: FollowUpQuestion;
  onAnswer: (questionId: string, answer: string) => void;
  isSubmitting: boolean;
}) {
  const [answer, setAnswer] = useState('');
  const fieldId = `answer-${question.id}`;

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!answer.trim()) return;
    onAnswer(question.id, answer.trim());
    setAnswer('');
  };

  if (question.answer) {
    return (
      <div className="flex flex-col gap-1 rounded-md border p-3">
        <p className="text-sm font-medium">{question.question}</p>
        <p className="text-sm text-muted-foreground">Answered: {question.answer}</p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2 rounded-md border p-3">
      <div>
        <p className="text-sm font-medium">{question.question}</p>
        <p className="text-xs text-muted-foreground">
          About: {FIELD_LABELS[question.field] ?? question.field}
        </p>
      </div>
      <label htmlFor={fieldId} className="sr-only">
        Answer: {question.question}
      </label>
      <textarea
        id={fieldId}
        rows={2}
        value={answer}
        onChange={(event) => setAnswer(event.target.value)}
        className="rounded-md border px-3 py-2 text-sm"
        placeholder="Your answer"
      />
      <button
        type="submit"
        disabled={isSubmitting || !answer.trim()}
        className="self-start rounded-md border px-3 py-1.5 text-xs font-medium disabled:opacity-60"
      >
        Answer
      </button>
    </form>
  );
}

export function FollowUpQuestionList({
  questions,
  onAnswer,
  isSubmitting,
}: FollowUpQuestionListProps) {
  if (questions.length === 0) {
    return <p className="text-sm text-muted-foreground">No follow-up questions right now.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {questions.map((question) => (
        <QuestionRow
          key={question.id}
          question={question}
          onAnswer={onAnswer}
          isSubmitting={isSubmitting}
        />
      ))}
    </div>
  );
}
