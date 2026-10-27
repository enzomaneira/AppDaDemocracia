import type { AgendaItem } from "../api/types";
import { formatDateTime } from "../lib/format";
import { Empty } from "./States";

export function AgendaList({ items }: { items: AgendaItem[] }) {
  if (!items.length) return <Empty title="Nenhum evento no período">A agenda cobre os próximos 14 dias e o último mês.</Empty>;
  const now = Date.now();
  const upcoming = items.filter((e) => new Date(e.starts_at).getTime() >= now).reverse();
  const past = items.filter((e) => new Date(e.starts_at).getTime() < now);
  return (
    <div className="flex flex-col gap-6">
      <Section title="Próximos dias" items={upcoming} empty="Nenhum evento agendado." />
      <Section title="Histórico" items={past} empty="Nenhum evento recente." />
    </div>
  );
}

function Section({ title, items, empty }: { title: string; items: AgendaItem[]; empty: string }) {
  return (
    <section>
      <h3 className="mb-2 text-sm font-semibold uppercase tracking-wide muted">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm muted">{empty}</p>
      ) : (
        <ol className="flex flex-col gap-2">
          {items.map((e) => (
            <li key={e.id} className="card flex gap-3">
              <time dateTime={e.starts_at} className="w-20 shrink-0 text-sm font-semibold tabular-nums">
                {formatDateTime(e.starts_at)}
              </time>
              <div className="min-w-0">
                <p className="text-sm">{e.title}</p>
                <p className="text-xs muted">
                  {[e.organ, e.location, e.status].filter(Boolean).join(" · ")}
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
