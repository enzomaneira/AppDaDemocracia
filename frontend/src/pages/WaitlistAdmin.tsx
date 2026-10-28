import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { downloadFile } from "../api/client";
import { useWaitlistSummary } from "../api/hooks";
import type { WaitlistSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Empty, ErrorBox, Loading } from "../components/States";
import { relativeTime } from "../lib/format";

/** Resultados da lista de espera (só admin): o que a população disse que precisa. */
export default function WaitlistAdmin() {
  const { user, loggedIn, loading } = useAuth();
  const summary = useWaitlistSummary(!!user?.is_admin);
  const [error, setError] = useState("");

  if (!loggedIn) return <Navigate to="/entrar" replace state={{ next: "/admin/lista" }} />;
  if (loading || !user) return <Loading />;
  if (!user.is_admin) return <Empty title="Acesso restrito a administradores" />;
  if (summary.isLoading) return <Loading />;
  if (summary.error || !summary.data) return <ErrorBox error={summary.error} />;
  const s = summary.data;

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold">Lista de espera</h1>
          <p className="text-sm muted">
            <span className="text-3xl font-bold tabular-nums text-slate-900 dark:text-slate-100">{s.total}</span>{" "}
            {s.total === 1 ? "inscrição" : "inscrições"} ·{" "}
            <Link to="/lista" className="underline">
              ver a página pública
            </Link>
          </p>
        </div>
        <button
          type="button"
          className="btn-secondary"
          onClick={() =>
            downloadFile("/admin/waitlist/export.csv", "lista-de-espera.csv").catch((e: Error) => setError(e.message))
          }
        >
          Baixar CSV
        </button>
      </div>
      {error && (
        <p role="alert" className="text-sm text-voto-nao">
          {error}
        </p>
      )}

      {s.total === 0 ? (
        <Empty title="Ninguém se inscreveu ainda">Compartilhe a página /lista para começar a receber respostas.</Empty>
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-3">
            <Breakdown title="Origem" data={s.by_source} total={s.total} />
            <Breakdown title="Estado" data={s.by_uf} total={s.total} limit={8} />
            <Breakdown title="Idade" data={s.by_age} total={s.total} />
          </div>
          {s.questions.map((q) => (
            <QuestionResult key={q.id} q={q} />
          ))}
          <OpenAnswers items={s.open_answers} />
        </>
      )}
    </div>
  );
}

function pct(n: number, total: number) {
  return total ? Math.round((n / total) * 100) : 0;
}

function Breakdown({ title, data, total, limit = 6 }: { title: string; data: Record<string, number>; total: number; limit?: number }) {
  const rows = Object.entries(data).slice(0, limit);
  return (
    <section className="card flex flex-col gap-2">
      <h2 className="text-sm font-semibold">{title}</h2>
      <ul className="flex flex-col gap-1 text-sm">
        {rows.map(([k, n]) => (
          <li key={k} className="flex justify-between gap-2">
            <span className="truncate">{k}</span>
            <span className="tabular-nums muted">
              {n} · {pct(n, total)}%
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

function QuestionResult({ q }: { q: WaitlistSummary["questions"][number] }) {
  const options = [...q.options].sort((a, b) => b.count - a.count);
  return (
    <section className="card flex flex-col gap-3" aria-label={q.text}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{q.text}</h2>
        <span className="text-xs muted">
          {q.answered} {q.answered === 1 ? "resposta" : "respostas"}
          {q.kind === "multi" && " · podia marcar mais de uma"}
        </span>
      </div>
      <ul className="flex flex-col gap-2">
        {options.map((o) => {
          const p = pct(o.count, q.answered);
          return (
            <li key={o.id} className="flex flex-col gap-1">
              <div className="flex justify-between gap-2 text-sm">
                <span>{o.label}</span>
                <span className="shrink-0 tabular-nums muted">
                  {o.count} · {p}%
                </span>
              </div>
              <div className="h-2 overflow-hidden rounded-full bg-slate-100 dark:bg-slate-800" aria-hidden="true">
                <div className="h-full rounded-full bg-marca" style={{ width: `${p}%` }} />
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function OpenAnswers({ items }: { items: WaitlistSummary["open_answers"] }) {
  return (
    <section className="card flex flex-col gap-3">
      <h2 className="font-semibold">O que faria a pessoa acompanhar mais a política</h2>
      {items.length === 0 ? (
        <p className="text-sm muted">Nenhuma resposta aberta ainda.</p>
      ) : (
        <ul className="flex flex-col divide-y divide-slate-100 dark:divide-slate-800">
          {items.map((a, i) => (
            <li key={i} className="py-2 text-sm">
              <p>“{a.text}”</p>
              <p className="text-xs muted">
                {a.uf ?? "UF não informada"} · {relativeTime(a.created_at)}
              </p>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
