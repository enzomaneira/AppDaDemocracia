import { useEffect, useId, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useCompare, useCompareVotes, usePolitician, useSearch } from "../api/hooks";
import type { PoliticianSummary, Stats } from "../api/types";
import { Avatar, PoliticianLine } from "../components/PoliticianCard";
import { Empty, ErrorBox, LoadMore, Loading } from "../components/States";
import { VoteBadge } from "../components/VoteBadge";
import { agreementText, barShares, rankByName } from "../lib/compare";
import { billLabel, formatBRL, formatDate, formatNumber, formatPercent, houseLabel } from "../lib/format";

type Side = "a" | "b";
const SIDE_COLOR: Record<Side, string> = { a: "bg-lado-a", b: "bg-lado-b" };
const SIDE_TEXT: Record<Side, string> = { a: "text-lado-a", b: "text-lado-b" };

function periodOptions(): [string, string][] {
  const year = new Date().getFullYear();
  return [["", "Legislatura atual"], ...[0, 1, 2, 3].map((d): [string, string] => [String(year - d), String(year - d)])];
}

export default function Compare() {
  const [params, setParams] = useSearchParams();
  const a = params.get("a") ?? "";
  const b = params.get("b") ?? "";
  const period = params.get("period") ?? "";

  const set = (key: string, value: string) =>
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );

  const cmp = useCompare(a, b, period || undefined);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <h1 className="text-2xl font-bold">Comparar parlamentares</h1>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Período</span>
          <select className="input" value={period} onChange={(e) => set("period", e.target.value)}>
            {periodOptions().map(([v, l]) => (
              <option key={v} value={v}>
                {l}
              </option>
            ))}
          </select>
        </label>
      </div>

      <section aria-label="Parlamentares comparados" className="grid grid-cols-[1fr_auto_1fr] items-start gap-2 sm:gap-4">
        <Slot side="a" slug={a} other={b} onChange={(v) => set("a", v)} />
        <span aria-hidden="true" className="mt-10 text-sm font-bold muted">
          vs
        </span>
        <Slot side="b" slug={b} other={a} onChange={(v) => set("b", v)} />
      </section>

      {a && b && a === b && <Empty title="Escolha dois parlamentares diferentes" />}
      {(!a || !b) && (
        <Empty title="Escolha dois parlamentares">
          Deputados e senadores podem ser comparados entre si. Votos em comum só existem entre parlamentares da mesma casa.
        </Empty>
      )}

      {cmp.isLoading && <Loading />}
      {cmp.error && <ErrorBox error={cmp.error} />}
      {cmp.data && (
        <>
          <Agreement data={cmp.data} />
          <Metrics a={cmp.data.stats_a} b={cmp.data.stats_b} sameHouse={cmp.data.same_house} />
          {cmp.data.same_house && <CommonVotes a={a} b={b} period={period || undefined} />}
          <p className="text-xs muted">
            Mesma metodologia para todos.{" "}
            <Link to="/como-calculamos" className="underline">
              Como calculamos
            </Link>
          </p>
        </>
      )}
    </div>
  );
}

/** Um lado da comparação: mostra o parlamentar escolhido ou a busca para escolher. */
function Slot({ side, slug, other, onChange }: { side: Side; slug: string; other: string; onChange: (v: string) => void }) {
  const { data: p } = usePolitician(slug);
  if (slug && p) {
    return (
      <div className="card flex flex-col items-center gap-2 text-center">
        <span className={`h-1 w-12 rounded-full ${SIDE_COLOR[side]}`} aria-hidden="true" />
        <Avatar p={p} size={64} />
        <Link to={`/politico/${p.slug}`} className="font-semibold hover:underline">
          {p.name}
        </Link>
        <PoliticianLine p={p} />
        <button type="button" className="text-sm text-marca underline" onClick={() => onChange("")}>
          Trocar
        </button>
      </div>
    );
  }
  return <Picker side={side} exclude={other} onPick={onChange} />;
}

function Picker({ side, exclude, onPick }: { side: Side; exclude: string; onPick: (slug: string) => void }) {
  const [text, setText] = useState("");
  const [q, setQ] = useState("");
  const id = useId();
  useEffect(() => {
    const t = setTimeout(() => setQ(text.trim()), 250);
    return () => clearTimeout(t);
  }, [text]);
  const res = useSearch({ q });
  const found = q.length >= 2 ? (res.data?.pages[0]?.items ?? []).filter((p) => p.slug !== exclude) : [];
  const items: PoliticianSummary[] = rankByName(found, q).slice(0, 6);

  return (
    <div className="card flex flex-col gap-2">
      <span className={`h-1 w-12 self-center rounded-full ${SIDE_COLOR[side]}`} aria-hidden="true" />
      <label htmlFor={id} className="text-sm font-medium">
        {side === "a" ? "Primeiro parlamentar" : "Segundo parlamentar"}
      </label>
      <input
        id={id}
        className="input"
        type="search"
        placeholder="Buscar por nome"
        value={text}
        onChange={(e) => setText(e.target.value)}
        autoComplete="off"
        aria-controls={`${id}-lista`}
      />
      {q.length >= 2 && (
        <ul id={`${id}-lista`} className="flex flex-col" aria-live="polite">
          {res.isLoading && <li className="text-sm muted">Buscando…</li>}
          {!res.isLoading && items.length === 0 && <li className="text-sm muted">Ninguém encontrado.</li>}
          {items.map((p) => (
            <li key={p.id}>
              <button
                type="button"
                onClick={() => onPick(p.slug)}
                className="flex w-full items-center gap-2 rounded-lg p-2 text-left hover:bg-slate-100 dark:hover:bg-slate-800"
              >
                <Avatar p={p} size={32} />
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold">{p.name}</span>
                  <span className="block truncate text-xs muted">
                    {houseLabel(p.house)} · {p.party}-{p.uf}
                  </span>
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function Agreement({ data }: { data: NonNullable<ReturnType<typeof useCompare>["data"]> }) {
  if (!data.same_house) {
    return (
      <section className="card text-sm">
        <p className="font-semibold">Casas diferentes</p>
        <p className="muted">
          {data.a.name} ({houseLabel(data.a.house)}) e {data.b.name} ({houseLabel(data.b.house)}) não votam as mesmas
          matérias, então não há votos em comum para comparar. As métricas abaixo usam a média da casa de cada um.
        </p>
      </section>
    );
  }
  return (
    <section className="card flex flex-col items-center gap-1 text-center" aria-label="Concordância nas votações">
      <p className="text-sm muted">Concordância nas votações em comum</p>
      <p className="text-4xl font-bold tabular-nums">{formatPercent(data.agreement_rate)}</p>
      <p className="text-sm muted">{agreementText(data.common_votes, data.divergent_votes)}</p>
    </section>
  );
}

interface Row {
  label: string;
  a: number | null;
  b: number | null;
  avgA: number | null;
  avgB: number | null;
  format: (v: number | null) => string;
  hint?: (s: Stats) => string;
}

function Metrics({ a, b, sameHouse }: { a: Stats; b: Stats; sameHouse: boolean }) {
  const rows: Row[] = [
    {
      label: "Presença em sessões deliberativas",
      a: a.attendance_rate.value,
      b: b.attendance_rate.value,
      avgA: a.attendance_rate.house_avg,
      avgB: b.attendance_rate.house_avg,
      format: formatPercent,
      hint: (s) => `${s.sessions_present} de ${s.sessions_total} · ${s.sessions_justified} justificadas`,
    },
    {
      label: "Votações nominais participadas",
      a: a.votes_participated.value,
      b: b.votes_participated.value,
      avgA: a.votes_participated.house_avg,
      avgB: b.votes_participated.house_avg,
      format: formatNumber,
      hint: (s) => `de ${s.votes_total}`,
    },
    {
      label: "Proposições apresentadas",
      a: a.bills_authored.value,
      b: b.bills_authored.value,
      avgA: a.bills_authored.house_avg,
      avgB: b.bills_authored.house_avg,
      format: formatNumber,
    },
    {
      label: "Gastos da cota parlamentar",
      a: a.expenses_total.value,
      b: b.expenses_total.value,
      avgA: a.expenses_total.house_avg,
      avgB: b.expenses_total.house_avg,
      format: formatBRL,
    },
  ];
  return (
    <section className="card flex flex-col gap-5" aria-label="Métricas lado a lado">
      <p className="text-sm muted">{a.period_label}</p>
      {rows.map((r) => (
        <MetricRow key={r.label} row={r} a={a} b={b} sameHouse={sameHouse} />
      ))}
    </section>
  );
}

function MetricRow({ row, a, b, sameHouse }: { row: Row; a: Stats; b: Stats; sameHouse: boolean }) {
  const [wa, wb] = barShares(row.a, row.b);
  return (
    <div className="flex flex-col gap-1.5">
      <p className="text-center text-sm font-medium">{row.label}</p>
      <div className="grid grid-cols-2 items-baseline gap-2">
        <span className={`text-lg font-bold tabular-nums ${SIDE_TEXT.a}`}>{row.format(row.a)}</span>
        <span className={`text-right text-lg font-bold tabular-nums ${SIDE_TEXT.b}`}>{row.format(row.b)}</span>
      </div>
      {/* Barras saem do centro, como num confronto; o texto acima é o dado, a barra é só apoio. */}
      <div className="grid grid-cols-2 gap-1" aria-hidden="true">
        <div className="flex h-2 justify-end overflow-hidden rounded-l-full bg-slate-100 dark:bg-slate-800">
          <div className={`${SIDE_COLOR.a} rounded-l-full`} style={{ width: `${wa}%` }} />
        </div>
        <div className="flex h-2 overflow-hidden rounded-r-full bg-slate-100 dark:bg-slate-800">
          <div className={`${SIDE_COLOR.b} rounded-r-full`} style={{ width: `${wb}%` }} />
        </div>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs muted">
        <span>{row.hint?.(a)}</span>
        <span className="text-right">{row.hint?.(b)}</span>
      </div>
      <p className="text-center text-xs muted">
        {sameHouse
          ? `Média da casa: ${row.format(row.avgA)}`
          : `Média da casa: ${row.format(row.avgA)} · ${row.format(row.avgB)}`}
      </p>
    </div>
  );
}

function CommonVotes({ a, b, period }: { a: string; b: string; period?: string }) {
  const [divergent, setDivergent] = useState(false);
  const q = useCompareVotes(a, b, period, divergent);
  const items = q.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <section className="flex flex-col gap-3" aria-label="Votações em comum">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-lg font-semibold">Votações em comum</h2>
        <div role="tablist" aria-label="Filtrar votações" className="flex gap-2">
          {[
            [false, "Todas"],
            [true, "Só divergências"],
          ].map(([value, label]) => (
            <button
              key={String(value)}
              role="tab"
              aria-selected={divergent === value}
              onClick={() => setDivergent(value as boolean)}
              className={`btn min-h-9 rounded-full px-4 ${divergent === value ? "bg-marca text-white" : "btn-secondary"}`}
            >
              {label as string}
            </button>
          ))}
        </div>
      </div>
      {q.isLoading ? (
        <Loading />
      ) : q.error ? (
        <ErrorBox error={q.error} />
      ) : items.length === 0 ? (
        <Empty title={divergent ? "Nenhuma divergência no período" : "Nenhuma votação em comum no período"} />
      ) : (
        <ul className="flex flex-col gap-2">
          {items.map(({ vote: v, choice_a, choice_b, agree }) => (
            <li key={v.id} className="card flex flex-col gap-2">
              <Link to={`/votacao/${v.id}`} className="text-sm hover:underline">
                {v.bill && <strong>{billLabel(v.bill)}: </strong>}
                {v.bill?.plain_summary ?? v.bill?.official_summary ?? v.description}
              </Link>
              <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
                <span className="justify-self-start">
                  <VoteBadge choice={choice_a} size="sm" />
                </span>
                <span className={`text-xs font-semibold ${agree ? "muted" : ""}`}>
                  {agree ? "= votaram igual" : "≠ divergiram"}
                </span>
                <span className="justify-self-end">
                  <VoteBadge choice={choice_b} size="sm" />
                </span>
              </div>
              <p className="text-xs muted">
                {formatDate(v.voted_at)}
                {v.result && ` · ${v.result}`}
              </p>
            </li>
          ))}
        </ul>
      )}
      <LoadMore hasNext={q.hasNextPage} loading={q.isFetchingNextPage} onClick={() => q.fetchNextPage()} />
    </section>
  );
}
