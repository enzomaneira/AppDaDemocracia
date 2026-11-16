import { useState } from "react";
import { Link } from "react-router-dom";

import { useFeed, useFollows } from "../api/hooks";
import type { FeedType } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { FeedItemCard } from "../components/FeedItemCard";
import { SurveyInvite } from "../components/SurveyInvite";
import { Avatar } from "../components/PoliticianCard";
import { Empty, ErrorBox, LoadMore, Loading, UpdatedAt } from "../components/States";
import { beginVisit, isNew, sinceLabel } from "../lib/lastVisit";

const FILTERS: [FeedType | "", string][] = [
  ["", "Tudo"],
  ["vote", "Votos"],
  ["bill", "Proposições"],
  ["agenda", "Agenda"],
  ["news", "Notícias"],
];

export default function Home() {
  const { loggedIn } = useAuth();
  return loggedIn ? <Feed /> : <Welcome />;
}

function Welcome() {
  return (
    <section className="flex flex-col gap-6 py-6">
      <div className="flex flex-col gap-3">
        <h1 className="text-3xl font-bold leading-tight">Acompanhe quem você elegeu, todo dia.</h1>
        <p className="muted">
          Votações, presença, agenda e notícias de deputados e senadores num só lugar. Todo número tem link para a
          fonte oficial, e as mesmas regras valem para todos.
        </p>
      </div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <Link to="/cadastro" className="btn-primary">
          Criar conta e seguir políticos
        </Link>
        <Link to="/buscar" className="btn-secondary">
          Só navegar
        </Link>
      </div>
      <ul className="grid gap-3 sm:grid-cols-3">
        {[
          ["Apartidário", "Sem nota, ranking ou selo de “bom político”."],
          ["Rastreável", "Cada dado leva à página oficial da Câmara ou do Senado."],
          ["Em contexto", "Ausências justificadas aparecem separadas das faltas."],
        ].map(([t, d]) => (
          <li key={t} className="card">
            <p className="font-semibold">{t}</p>
            <p className="text-sm muted">{d}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function Feed() {
  const [type, setType] = useState<FeedType | "">("");
  // Corte do selo de novidades: fixado ao abrir o Início, para não mudar enquanto a pessoa lê.
  const [since] = useState(() => beginVisit());
  const follows = useFollows();
  const feed = useFeed(type, (follows.data?.length ?? 0) > 0);

  if (follows.isLoading) return <Loading />;
  if (follows.error) return <ErrorBox error={follows.error} />;
  if (!follows.data?.length) {
    return (
      <Empty title="Você ainda não segue ninguém">
        <p className="mb-4">Escolha seu estado para ver os parlamentares que o representam.</p>
        <Link to="/comecar" className="btn-primary">
          Escolher parlamentares
        </Link>
      </Empty>
    );
  }

  const items = feed.data?.pages.flatMap((p) => p.items) ?? [];
  const fresh = items.filter((i) => isNew(i.occurred_at, since));
  const withNews = new Set(fresh.map((i) => i.politician.id));
  // Se tudo o que já carregou é novo e ainda há páginas, o total pode ser maior.
  const more = fresh.length === items.length && feed.hasNextPage ? "+" : "";
  return (
    <div className="flex flex-col gap-4">
      <SurveyInvite />
      <section aria-label="Seguindo">
        <h2 className="mb-2 text-sm font-semibold muted">Seguindo</h2>
        <ul className="-mx-4 flex gap-3 overflow-x-auto px-4 pb-1">
          {follows.data.map((f) => (
            <li key={f.politician.id}>
              <Link to={`/politico/${f.politician.slug}`} className="flex w-16 flex-col items-center gap-1 text-center">
                <span className="relative">
                  <Avatar p={f.politician} size={52} />
                  {withNews.has(f.politician.id) && (
                    <span
                      aria-hidden="true"
                      className="absolute right-0 top-0 size-3 rounded-full border-2 border-white bg-marca dark:border-slate-950"
                    />
                  )}
                </span>
                <span className="line-clamp-2 text-xs">
                  {f.politician.name}
                  {withNews.has(f.politician.id) && <span className="sr-only"> (tem novidade)</span>}
                </span>
              </Link>
            </li>
          ))}
          <li>
            <Link to="/buscar" className="flex w-16 flex-col items-center gap-1 text-center" aria-label="Seguir mais">
              <span className="grid size-[52px] place-items-center rounded-full border-2 border-dashed border-slate-300 text-xl dark:border-slate-700">
                +
              </span>
              <span className="text-xs">Seguir</span>
            </Link>
          </li>
        </ul>
      </section>

      <div role="tablist" aria-label="Filtrar feed" className="-mx-4 flex gap-2 overflow-x-auto px-4">
        {FILTERS.map(([value, label]) => (
          <button
            key={value}
            role="tab"
            aria-selected={type === value}
            onClick={() => setType(value)}
            className={`btn min-h-9 shrink-0 rounded-full px-4 ${type === value ? "bg-marca text-white" : "btn-secondary"}`}
          >
            {label}
          </button>
        ))}
      </div>
      <UpdatedAt />

      {feed.isLoading ? (
        <Loading />
      ) : feed.error ? (
        <ErrorBox error={feed.error} />
      ) : items.length === 0 ? (
        <Empty title="Nada por aqui ainda">Novidades aparecem depois da sincronização diária com as fontes oficiais.</Empty>
      ) : (
        <>
          {since && fresh.length > 0 && (
            <p className="text-sm font-semibold" role="status">
              {fresh.length}
              {more} {fresh.length === 1 && !more ? "novidade" : "novidades"} {sinceLabel(since)}
            </p>
          )}
          <ul className="flex flex-col gap-3">
            {items.map((i) => (
              <FeedItemCard key={i.id} item={i} isNew={isNew(i.occurred_at, since)} />
            ))}
          </ul>
        </>
      )}
      <LoadMore hasNext={feed.hasNextPage} loading={feed.isFetchingNextPage} onClick={() => feed.fetchNextPage()} />
    </div>
  );
}
