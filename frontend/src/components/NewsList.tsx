import type { NewsItem } from "../api/types";
import { relativeTime } from "../lib/format";

/** Só título, trecho curto, fonte e link para o veículo (sem copiar a matéria). */
export function NewsList({ items, showPoliticians }: { items: NewsItem[]; showPoliticians?: boolean }) {
  return (
    <ul className="flex flex-col gap-3">
      {items.map((n) => (
        <li key={n.id} className="card">
          <a href={n.url} target="_blank" rel="noopener noreferrer" className="font-semibold hover:underline">
            {n.title}
            <span className="sr-only"> (abre em nova aba)</span>
          </a>
          {n.snippet && <p className="mt-1 text-sm muted">{n.snippet}</p>}
          <p className="mt-2 text-xs muted">
            {n.source_name ?? "Fonte"} · {relativeTime(n.published_at)}
            {showPoliticians && n.politicians.length > 0 && <> · cita {n.politicians.map((p) => p.name).join(", ")}</>}
          </p>
        </li>
      ))}
    </ul>
  );
}
