import { Link, useParams } from "react-router-dom";

import { useVote } from "../api/hooks";
import type { VoteChoice } from "../api/types";
import { Avatar } from "../components/PoliticianCard";
import { ErrorBox, Loading } from "../components/States";
import { VoteBadge } from "../components/VoteBadge";
import { billLabel, formatDateTime, houseLabel, VOTE_LABEL } from "../lib/format";

const BASE: VoteChoice[] = ["sim", "nao", "abstencao", "obstrucao", "ausente"];
// Estados que só aparecem no Senado (comparecimento vem no registro de cada votação).
const EXTRA: VoteChoice[] = ["secreto", "presente", "justificada", "art17"];

/** Categorias do placar: as básicas sempre; as do Senado só quando houver. */
export function placar(tally: Record<string, number>): VoteChoice[] {
  return [...BASE, ...EXTRA.filter((c) => (tally[c] ?? 0) > 0)];
}

export default function Vote() {
  const { id = "" } = useParams();
  const { data: v, isLoading, error } = useVote(id);
  if (isLoading) return <Loading />;
  if (error || !v) return <ErrorBox error={error} />;

  const tally = v.records.reduce<Record<string, number>>((acc, r) => {
    acc[r.choice] = (acc[r.choice] ?? 0) + 1;
    return acc;
  }, {});
  const followed = v.records.filter((r) => r.is_followed);
  const others = v.records.filter((r) => !r.is_followed);

  return (
    <div className="flex flex-col gap-4">
      <section className="card flex flex-col gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide muted">
          Votação nominal · {houseLabel(v.house)} · {formatDateTime(v.voted_at)}
        </p>
        {v.bill && <h1 className="text-xl font-bold">{billLabel(v.bill)}</h1>}
        {v.bill?.plain_summary && (
          <p>
            {v.bill.plain_summary}
            {v.bill.plain_summary_ai && <span className="ml-1 text-xs muted">(resumo gerado por IA)</span>}
          </p>
        )}
        {v.bill?.official_summary && <p className="text-sm muted">Ementa oficial: {v.bill.official_summary}</p>}
        {v.description && <p className="text-sm">{v.description}</p>}
        {v.result && <p className="font-semibold">Resultado: {v.result}</p>}
        <div className="flex flex-wrap gap-2 pt-1 text-sm">
          <a href={v.source_url} target="_blank" rel="noopener noreferrer" className="text-marca underline">
            Fonte oficial ↗
          </a>
          {v.bill?.url && (
            <a href={v.bill.url} target="_blank" rel="noopener noreferrer" className="text-marca underline">
              Ver proposição ↗
            </a>
          )}
        </div>
      </section>

      <section className="card" aria-label="Placar">
        <h2 className="mb-3 font-semibold">Placar</h2>
        <dl className="grid grid-cols-3 gap-2 text-center sm:grid-cols-5">
          {placar(tally).map((c) => (
            <div key={c} className="flex flex-col items-center gap-1">
              <dt>
                <VoteBadge choice={c} size="sm" />
              </dt>
              <dd className="text-2xl font-bold tabular-nums" aria-label={`${tally[c] ?? 0} votos ${VOTE_LABEL[c]}`}>
                {tally[c] ?? 0}
              </dd>
            </div>
          ))}
        </dl>
      </section>

      {followed.length > 0 && <RecordList title="Quem você segue" records={followed} highlight />}
      <RecordList title={followed.length ? "Demais parlamentares" : "Votos nominais"} records={others} />
    </div>
  );
}

function RecordList({
  title,
  records,
  highlight,
}: {
  title: string;
  records: NonNullable<ReturnType<typeof useVote>["data"]>["records"];
  highlight?: boolean;
}) {
  return (
    <section>
      <h2 className="mb-2 font-semibold">{title}</h2>
      <ul className={`flex flex-col divide-y divide-slate-100 rounded-2xl border bg-white dark:divide-slate-800 dark:bg-slate-900 ${highlight ? "border-marca/50" : "border-slate-200 dark:border-slate-800"}`}>
        {records.map((r) => (
          <li key={r.politician.id} className="flex items-center gap-3 px-4 py-2">
            <Avatar p={r.politician} size={36} />
            <Link to={`/politico/${r.politician.slug}`} className="min-w-0 flex-1 truncate text-sm hover:underline">
              {r.politician.name}{" "}
              <span className="muted">
                · {r.politician.party}-{r.politician.uf}
              </span>
            </Link>
            <VoteBadge choice={r.choice} size="sm" />
          </li>
        ))}
      </ul>
    </section>
  );
}
