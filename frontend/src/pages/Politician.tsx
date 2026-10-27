import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import {
  useAgenda,
  useExpenses,
  usePolitician,
  usePoliticianNews,
  usePoliticianVotes,
  useStats,
} from "../api/hooks";
import type { PoliticianProfile } from "../api/types";
import { AgendaList } from "../components/AgendaList";
import { FollowButton } from "../components/FollowButton";
import { NewsList } from "../components/NewsList";
import { Avatar, PoliticianLine } from "../components/PoliticianCard";
import { StatTile } from "../components/StatTile";
import { Empty, ErrorBox, LoadMore, Loading, UpdatedAt } from "../components/States";
import { VoteBadge } from "../components/VoteBadge";
import { billLabel, formatBRL, formatDate, formatNumber, formatPercent } from "../lib/format";

const TABS = [
  ["desempenho", "Desempenho"],
  ["votacoes", "Votações"],
  ["agenda", "Agenda"],
  ["noticias", "Notícias"],
] as const;
type Tab = (typeof TABS)[number][0];

export default function Politician() {
  const { slug = "" } = useParams();
  const [tab, setTab] = useState<Tab>("desempenho");
  const { data: p, isLoading, error } = usePolitician(slug);

  if (isLoading) return <Loading />;
  if (error || !p) return <ErrorBox error={error} />;

  return (
    <div className="flex flex-col gap-4">
      <Header p={p} />
      <div role="tablist" aria-label="Seções do perfil" className="-mx-4 flex overflow-x-auto border-b border-slate-200 px-4 dark:border-slate-800">
        {TABS.map(([id, label]) => (
          <button
            key={id}
            role="tab"
            id={`tab-${id}`}
            aria-selected={tab === id}
            aria-controls={`panel-${id}`}
            onClick={() => setTab(id)}
            className={`min-h-11 shrink-0 border-b-2 px-4 text-sm font-semibold ${tab === id ? "border-marca text-marca" : "border-transparent muted"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`}>
        {tab === "desempenho" && <Performance slug={slug} />}
        {tab === "votacoes" && <Votes slug={slug} />}
        {tab === "agenda" && <AgendaTab slug={slug} />}
        {tab === "noticias" && <NewsTab slug={slug} />}
      </div>
    </div>
  );
}

function Header({ p }: { p: PoliticianProfile }) {
  return (
    <section className="card flex flex-col gap-4">
      <div className="flex items-center gap-4">
        <Avatar p={p} size={80} />
        <div className="min-w-0 flex-1">
          <h1 className="text-xl font-bold">{p.name}</h1>
          <PoliticianLine p={p} />
          {p.civil_name !== p.name && <p className="text-xs muted">Nome civil: {p.civil_name}</p>}
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <FollowButton id={p.id} following={p.is_following} name={p.name} />
        <a href={p.official_url} target="_blank" rel="noopener noreferrer" className="btn-secondary">
          Página oficial ↗
        </a>
        {p.email && (
          <a href={`mailto:${p.email}`} className="btn-secondary">
            E-mail do gabinete
          </a>
        )}
      </div>
      {p.social_links.length > 0 && (
        <ul className="flex flex-wrap gap-x-3 gap-y-1 text-sm">
          {p.social_links.map((url) => (
            <li key={url}>
              <a href={url} target="_blank" rel="noopener noreferrer" className="text-marca underline">
                {new URL(url).hostname.replace("www.", "")}
              </a>
            </li>
          ))}
        </ul>
      )}
      {p.legislature && <p className="text-xs muted">Mandato na {p.legislature}ª legislatura</p>}
    </section>
  );
}

function periodOptions() {
  const year = new Date().getFullYear();
  return [
    ["", "Legislatura atual"],
    ...[0, 1, 2, 3].map((d) => [String(year - d), String(year - d)]),
  ] as [string, string][];
}

function Performance({ slug }: { slug: string }) {
  const [period, setPeriod] = useState("");
  const { data: s, isLoading, error } = useStats(slug, period || undefined);
  const year = period ? Number(period) : new Date().getFullYear();
  const exp = useExpenses(slug, year);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Período</span>
          <select className="input" value={period} onChange={(e) => setPeriod(e.target.value)}>
            {periodOptions().map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
        <Link to="/como-calculamos" className="text-sm text-marca underline">
          Como calculamos
        </Link>
      </div>

      {isLoading ? (
        <Loading />
      ) : error || !s ? (
        <ErrorBox error={error} />
      ) : (
        <>
          <p className="text-sm muted">Período: {s.period_label}</p>
          <div className="grid gap-3 sm:grid-cols-2">
            <StatTile
              label="Presença em sessões deliberativas"
              value={s.attendance_rate.value}
              avg={s.attendance_rate.house_avg}
              format={formatPercent}
              hint={`${s.sessions_present} presenças · ${s.sessions_absent} faltas · ${s.sessions_justified} ausências justificadas · ${s.sessions_total} sessões`}
            />
            <StatTile
              label="Votações nominais participadas"
              value={s.votes_participated.value}
              avg={s.votes_participated.house_avg}
              format={formatNumber}
              hint={`de ${s.votes_total} votações nominais no período`}
            />
            <StatTile
              label="Proposições apresentadas"
              value={s.bills_authored.value}
              avg={s.bills_authored.house_avg}
              format={formatNumber}
              hint={s.bills_reported ? `${s.bills_reported} relatadas` : undefined}
            />
            <StatTile
              label="Gastos da cota parlamentar"
              value={s.expenses_total.value}
              avg={s.expenses_total.house_avg}
              format={formatBRL}
            />
          </div>
          <UpdatedAt job="refresh_stats" />
        </>
      )}

      <section className="card flex flex-col gap-3">
        <h2 className="font-semibold">Cota parlamentar em {year}</h2>
        {exp.isLoading ? (
          <Loading />
        ) : exp.data && exp.data.by_category.length > 0 ? (
          <>
            <p className="text-2xl font-bold tabular-nums">{formatBRL(exp.data.total)}</p>
            <div className="h-48" aria-hidden="true">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={exp.data.by_month}>
                  <XAxis dataKey="month" tickLine={false} axisLine={false} fontSize={12} />
                  <YAxis hide />
                  <Tooltip formatter={(v: number) => formatBRL(v)} labelFormatter={(m) => `Mês ${m}`} />
                  <Bar dataKey="total" fill="var(--color-marca)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
            <table className="w-full text-sm">
              <caption className="sr-only">Gastos por categoria</caption>
              <thead>
                <tr className="text-left muted">
                  <th className="py-1 font-medium">Categoria</th>
                  <th className="py-1 text-right font-medium">Total</th>
                </tr>
              </thead>
              <tbody>
                {exp.data.by_category.map((c) => (
                  <tr key={c.category} className="border-t border-slate-100 dark:border-slate-800">
                    <td className="py-1.5 pr-2">{c.category}</td>
                    <td className="py-1.5 text-right tabular-nums">{formatBRL(c.total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : (
          <p className="text-sm muted">Nenhum gasto registrado neste ano.</p>
        )}
      </section>
    </div>
  );
}

function Votes({ slug }: { slug: string }) {
  const q = usePoliticianVotes(slug);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];
  if (!items.length) return <Empty title="Nenhuma votação nominal registrada" />;
  return (
    <div className="flex flex-col gap-3">
      <ul className="flex flex-col gap-3">
        {items.map(({ vote: v, choice, party_orientation, with_party }) => (
          <li key={v.id} className="card flex flex-col gap-2">
            <div className="flex items-start justify-between gap-3">
              <Link to={`/votacao/${v.id}`} className="text-sm hover:underline">
                {v.bill && <strong>{billLabel(v.bill)}: </strong>}
                {v.bill?.plain_summary ?? v.bill?.official_summary ?? v.description}
              </Link>
              <VoteBadge choice={choice} />
            </div>
            <p className="text-xs muted">
              {formatDate(v.voted_at)}
              {v.result && ` · ${v.result}`}
              {party_orientation && ` · orientação do partido: ${party_orientation}`}
              {with_party != null && (with_party ? " · votou com o partido" : " · votou diferente do partido")}
            </p>
          </li>
        ))}
      </ul>
      <LoadMore hasNext={q.hasNextPage} loading={q.isFetchingNextPage} onClick={() => q.fetchNextPage()} />
    </div>
  );
}

function AgendaTab({ slug }: { slug: string }) {
  const q = useAgenda(slug);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  return <AgendaList items={q.data ?? []} />;
}

function NewsTab({ slug }: { slug: string }) {
  const q = usePoliticianNews(slug);
  if (q.isLoading) return <Loading />;
  if (q.error) return <ErrorBox error={q.error} />;
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];
  if (!items.length) return <Empty title="Nenhuma notícia vinculada ainda" />;
  return (
    <div className="flex flex-col gap-3">
      <NewsList items={items} />
      <LoadMore hasNext={q.hasNextPage} loading={q.isFetchingNextPage} onClick={() => q.fetchNextPage()} />
    </div>
  );
}
