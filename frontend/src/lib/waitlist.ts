import type { SurveyQuestion } from "../api/types";

export type Answers = Record<string, string[] | string>;

/**
 * Marca/desmarca uma opção. Escolha única troca a resposta (clicar de novo desmarca);
 * múltipla escolha respeita o máximo: no limite, novas opções são ignoradas.
 */
export function toggleChoice(answers: Answers, q: SurveyQuestion, optionId: string): Answers {
  const current = answers[q.id];
  if (q.kind === "single") {
    const next = { ...answers };
    if (current === optionId) delete next[q.id];
    else next[q.id] = optionId;
    return next;
  }
  const list = Array.isArray(current) ? current : [];
  if (list.includes(optionId)) {
    const rest = list.filter((o) => o !== optionId);
    const next = { ...answers };
    if (rest.length) next[q.id] = rest;
    else delete next[q.id];
    return next;
  }
  if (q.max && list.length >= q.max) return answers;
  return { ...answers, [q.id]: [...list, optionId] };
}

export function isChosen(answers: Answers, q: SurveyQuestion, optionId: string) {
  const v = answers[q.id];
  return Array.isArray(v) ? v.includes(optionId) : v === optionId;
}

export function atLimit(answers: Answers, q: SurveyQuestion) {
  const v = answers[q.id];
  return q.kind === "multi" && !!q.max && Array.isArray(v) && v.length >= q.max;
}

/** Quantas perguntas fechadas foram respondidas (barra de progresso). */
export function answeredCount(answers: Answers, questions: SurveyQuestion[]) {
  return questions.filter((q) => q.kind !== "text" && answers[q.id] && answers[q.id].length > 0).length;
}

/** Origem da visita (?ref=instagram ou utm_source), para saber o que traz inscrições. */
export function sourceFromUrl(search: string): string | undefined {
  const p = new URLSearchParams(search);
  const raw = p.get("ref") ?? p.get("utm_source") ?? "";
  const clean = raw.toLowerCase().replace(/[^a-z0-9_-]/g, "").slice(0, 60);
  return clean || undefined;
}
