import { Link } from "react-router-dom";

import type { FeedItem, VoteChoice } from "../api/types";
import { formatDateTime, relativeTime } from "../lib/format";
import { Avatar } from "./PoliticianCard";
import { VoteBadge } from "./VoteBadge";

const TYPE_LABEL = { vote: "Votou", agenda: "Agenda", news: "Notícia", bill: "Apresentou proposição" } as const;

export function FeedItemCard({ item, isNew = false }: { item: FeedItem; isNew?: boolean }) {
  const p = item.politician;
  const pl = item.payload;
  return (
    <li className={`card flex gap-3 ${isNew ? "border-l-4 border-l-marca" : ""}`}>
      <Avatar p={p} size={40} />
      <div className="min-w-0 flex-1">
        <p className="text-sm">
          {isNew && (
            <span className="mr-2 rounded-full bg-marca px-2 py-0.5 text-xs font-semibold text-white">Novo</span>
          )}
          <Link to={`/politico/${p.slug}`} className="font-semibold hover:underline">
            {p.name}
          </Link>{" "}
          <span className="muted">
            · {TYPE_LABEL[item.type]} ·{" "}
            <time dateTime={item.occurred_at}>{relativeTime(item.occurred_at)}</time>
          </span>
        </p>
        <Body item={item} />
        {item.type === "vote" && pl.choice && (
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs muted">
            <VoteBadge choice={pl.choice as VoteChoice} size="sm" />
            {pl.party_orientation && <span>Orientação do partido: {pl.party_orientation}</span>}
            {pl.result && <span>· {pl.result}</span>}
          </div>
        )}
      </div>
    </li>
  );
}

function Body({ item }: { item: FeedItem }) {
  const pl = item.payload;
  switch (item.type) {
    case "vote":
      return (
        <Link to={`/votacao/${pl.ref_id}`} className="mt-1 block text-sm hover:underline">
          {pl.bill && <strong>{pl.bill}: </strong>}
          {pl.title}
        </Link>
      );
    case "agenda":
      return (
        <p className="mt-1 text-sm">
          {pl.title}
          {pl.starts_at && <span className="muted"> · {formatDateTime(pl.starts_at)}</span>}
          {pl.organ && <span className="muted"> · {pl.organ}</span>}
        </p>
      );
    case "news":
      return (
        <a href={pl.url ?? "#"} target="_blank" rel="noopener noreferrer" className="mt-1 block text-sm hover:underline">
          {pl.title} <span className="muted">· {pl.source}</span>
        </a>
      );
    case "bill":
      return (
        <a href={pl.url ?? "#"} target="_blank" rel="noopener noreferrer" className="mt-1 block text-sm hover:underline">
          <strong>{pl.bill}: </strong>
          {pl.title}
        </a>
      );
  }
}
