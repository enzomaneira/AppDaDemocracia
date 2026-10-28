import { useState, type FormEvent } from "react";

import type { SurveyQuestion } from "../api/types";
import { answeredCount, atLimit, isChosen, toggleChoice, type Answers } from "../lib/survey";

/** Formulário da pesquisa (todas as perguntas opcionais). Quem usa decide o que fazer ao enviar. */
export function SurveyForm({
  questions,
  initial,
  submitLabel,
  busy,
  error,
  onSubmit,
  secondary,
}: {
  questions: SurveyQuestion[];
  initial: Answers;
  submitLabel: string;
  busy: boolean;
  error: string;
  onSubmit: (answers: Answers) => void;
  secondary?: React.ReactNode;
}) {
  const [answers, setAnswers] = useState<Answers>(initial);
  const closed = questions.filter((q) => q.kind !== "text");
  const answered = answeredCount(answers, questions);

  function submit(e: FormEvent) {
    e.preventDefault();
    onSubmit(answers);
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-3">
      <p className="self-end text-sm muted" aria-live="polite">
        {answered} de {closed.length} respondidas · todas opcionais
      </p>
      {questions.map((q, i) => (
        <Question key={q.id} n={i + 1} q={q} answers={answers} setAnswers={setAnswers} />
      ))}
      {error && (
        <p role="alert" className="text-sm text-voto-nao">
          {error}
        </p>
      )}
      <div className="sticky bottom-16 flex flex-wrap gap-2 rounded-2xl bg-slate-50/90 py-3 backdrop-blur sm:bottom-0 dark:bg-slate-950/90">
        <button className="btn-primary flex-1" disabled={busy}>
          {busy ? "Enviando…" : submitLabel}
        </button>
        {secondary}
      </div>
    </form>
  );
}

function Question({
  n,
  q,
  answers,
  setAnswers,
}: {
  n: number;
  q: SurveyQuestion;
  answers: Answers;
  setAnswers: (fn: (a: Answers) => Answers) => void;
}) {
  if (q.kind === "text") {
    const value = (answers[q.id] as string) ?? "";
    return (
      <label className="card flex flex-col gap-2">
        <span className="font-medium">
          {n}. {q.text}
        </span>
        <textarea
          className="input min-h-24 py-2"
          maxLength={q.max_length ?? 500}
          value={value}
          onChange={(e) => {
            const v = e.target.value;
            setAnswers((a) => ({ ...a, [q.id]: v }));
          }}
        />
        <span className="self-end text-xs muted tabular-nums">
          {value.length}/{q.max_length}
        </span>
      </label>
    );
  }
  const limit = atLimit(answers, q);
  const hint = q.kind === "single" ? "Escolha uma" : q.max ? `Escolha até ${q.max}` : "Escolha quantas quiser";
  return (
    <fieldset className="card flex flex-col gap-3">
      <legend className="sr-only">{q.text}</legend>
      <p className="font-medium" aria-hidden="true">
        {n}. {q.text}
      </p>
      <p className="text-xs muted">{hint}</p>
      <div className="flex flex-wrap gap-2">
        {q.options.map((o) => {
          const on = isChosen(answers, q, o.id);
          const disabled = !on && limit;
          return (
            <button
              key={o.id}
              type="button"
              role={q.kind === "single" ? "radio" : "checkbox"}
              aria-checked={on}
              disabled={disabled}
              onClick={() => setAnswers((a) => toggleChoice(a, q, o.id))}
              className={`btn min-h-11 rounded-full px-4 text-left ${on ? "bg-marca text-white" : "btn-secondary"} ${disabled ? "opacity-40" : ""}`}
            >
              {on && <span aria-hidden="true">✓</span>}
              {o.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
