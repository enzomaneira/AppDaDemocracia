import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";

import { api } from "../api/client";
import { useSurvey, useWaitlistCount } from "../api/hooks";
import type { SurveyQuestion } from "../api/types";
import { ErrorBox, Loading } from "../components/States";
import { UFS } from "../lib/ufs";
import { answeredCount, atLimit, isChosen, sourceFromUrl, toggleChoice, type Answers } from "../lib/waitlist";

const BENEFITS = [
  ["Tudo num lugar só", "Votos, presença, gastos, projetos e agenda de quem você escolher acompanhar."],
  ["Em linguagem simples", "Sem juridiquês: o que foi votado e o que muda na sua vida."],
  ["Com a fonte oficial", "Cada número leva à Câmara ou ao Senado. Sem nota, ranking ou opinião."],
] as const;

export default function Waitlist() {
  const survey = useSurvey();
  const count = useWaitlistCount();
  const { search } = useLocation();
  const [done, setDone] = useState<{ position: number; updated: boolean } | null>(null);

  return (
    <div className="flex flex-col gap-8 py-2">
      <section className="flex flex-col gap-4">
        <p className="text-sm font-semibold uppercase tracking-wide text-marca">Lista de espera</p>
        <h1 className="text-3xl font-bold leading-tight sm:text-4xl">
          Política sem complicação. Saiba o que seus representantes fazem por você.
        </h1>
        <p className="muted">
          Estamos construindo o App da Democracia com quem vai usar. Entre na lista e conte, em 2 minutos, o que
          faria você acompanhar mais a política: suas respostas definem o que vem primeiro.
        </p>
        {!!count.data?.total && (
          <p className="text-sm font-medium">
            <span className="tabular-nums">{count.data.total.toLocaleString("pt-BR")}</span>{" "}
            {count.data.total === 1 ? "pessoa já entrou" : "pessoas já entraram"} na lista
          </p>
        )}
      </section>

      <ul className="grid gap-3 sm:grid-cols-3">
        {BENEFITS.map(([t, d]) => (
          <li key={t} className="card">
            <p className="font-semibold">{t}</p>
            <p className="text-sm muted">{d}</p>
          </li>
        ))}
      </ul>

      {done ? (
        <Thanks position={done.position} updated={done.updated} />
      ) : survey.isLoading ? (
        <Loading />
      ) : survey.error || !survey.data ? (
        <ErrorBox error={survey.error} />
      ) : (
        <SignupForm
          questions={survey.data.questions}
          ages={survey.data.age_ranges}
          source={sourceFromUrl(search)}
          onDone={setDone}
        />
      )}
    </div>
  );
}

function SignupForm({
  questions,
  ages,
  source,
  onDone,
}: {
  questions: SurveyQuestion[];
  ages: { id: string; label: string }[];
  source?: string;
  onDone: (r: { position: number; updated: boolean }) => void;
}) {
  const [answers, setAnswers] = useState<Answers>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const closed = questions.filter((q) => q.kind !== "text");
  const answered = answeredCount(answers, questions);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      const r = await api<{ position: number; updated: boolean }>("/waitlist", {
        method: "POST",
        body: JSON.stringify({
          email: String(f.get("email")),
          name: String(f.get("name") || "") || undefined,
          uf: String(f.get("uf") || "") || undefined,
          age_range: String(f.get("age") || "") || undefined,
          answers,
          accept_privacy: f.get("privacy") === "on",
          source,
        }),
      });
      onDone(r);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível enviar. Tente de novo.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      <fieldset className="card flex flex-col gap-3">
        <legend className="px-1 text-lg font-semibold">1. Seus dados</legend>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">E-mail *</span>
          <input className="input" name="email" type="email" autoComplete="email" required />
        </label>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Nome (opcional)</span>
          <input className="input" name="name" autoComplete="given-name" maxLength={120} />
        </label>
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Estado (opcional)</span>
            <select className="input" name="uf" defaultValue="">
              <option value="">—</option>
              {UFS.map(([s, n]) => (
                <option key={s} value={s}>
                  {n}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Idade (opcional)</span>
            <select className="input" name="age" defaultValue="">
              <option value="">—</option>
              {ages.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
        </div>
      </fieldset>

      <section className="flex flex-col gap-3" aria-labelledby="pesquisa">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <h2 id="pesquisa" className="text-lg font-semibold">
            2. Conte o que você precisa
          </h2>
          <span className="text-sm muted" aria-live="polite">
            {answered} de {closed.length} respondidas · todas opcionais
          </span>
        </div>
        {questions.map((q, i) => (
          <Question key={q.id} n={i + 1} q={q} answers={answers} setAnswers={setAnswers} />
        ))}
      </section>

      <div className="card flex flex-col gap-3">
        <label className="flex items-start gap-2 text-sm">
          <input type="checkbox" name="privacy" required className="mt-1 size-4" />
          <span>
            Aceito a{" "}
            <Link to="/privacidade" className="text-marca underline">
              política de privacidade
            </Link>
            . Usamos seu e-mail só para avisar do lançamento e as respostas, de forma agregada, para decidir o que
            construir. Não perguntamos partido nem voto.
          </span>
        </label>
        {error && (
          <p role="alert" className="text-sm text-voto-nao">
            {error}
          </p>
        )}
        <button className="btn-primary" disabled={busy}>
          {busy ? "Enviando…" : "Entrar na lista de espera"}
        </button>
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

function Thanks({ position, updated }: { position: number; updated: boolean }) {
  const [copied, setCopied] = useState(false);
  const url = `${location.origin}/lista?ref=indicacao`;

  async function share() {
    const text = "Entrei na lista do App da Democracia: acompanhar deputados e senadores com dados oficiais.";
    try {
      if (navigator.share) await navigator.share({ title: "App da Democracia", text, url });
      else {
        await navigator.clipboard.writeText(url);
        setCopied(true);
      }
    } catch {
      /* compartilhamento cancelado */
    }
  }

  return (
    <section className="card flex flex-col items-center gap-3 py-8 text-center" role="status">
      <p className="text-4xl" aria-hidden="true">
        ✓
      </p>
      <h2 className="text-2xl font-bold">{updated ? "Respostas atualizadas!" : "Você está na lista!"}</h2>
      <p className="muted">
        Sua posição: <strong className="tabular-nums">#{position.toLocaleString("pt-BR")}</strong>. Vamos avisar por
        e-mail quando o app estiver pronto para você.
      </p>
      <p className="text-sm muted">Quanto mais gente responder, melhor fica o que vamos construir.</p>
      <div className="flex flex-wrap justify-center gap-2">
        <button type="button" className="btn-primary" onClick={share}>
          {copied ? "Link copiado!" : "Convidar amigos"}
        </button>
        <Link to="/buscar" className="btn-secondary">
          Explorar o app agora
        </Link>
      </div>
    </section>
  );
}
