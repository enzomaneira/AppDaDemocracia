import type { ReactNode } from "react";

import { useDataStatus } from "../api/hooks";
import { relativeTime } from "../lib/format";

export function Loading({ label = "Carregando…" }: { label?: string }) {
  return (
    <div role="status" className="flex flex-col gap-3 py-4" aria-live="polite">
      <span className="sr-only">{label}</span>
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-20 animate-pulse rounded-2xl bg-slate-200 dark:bg-slate-800" />
      ))}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="card flex flex-col items-center gap-2 py-10 text-center">
      <p className="font-semibold">{title}</p>
      {children && <div className="text-sm muted">{children}</div>}
    </div>
  );
}

export function ErrorBox({ error }: { error: unknown }) {
  const msg = error instanceof Error ? error.message : "Algo deu errado.";
  return (
    <div role="alert" className="card border-voto-nao/40 text-sm">
      <p className="font-semibold">Não foi possível carregar.</p>
      <p className="muted">{msg}</p>
    </div>
  );
}

export function LoadMore({ hasNext, loading, onClick }: { hasNext?: boolean; loading: boolean; onClick: () => void }) {
  if (!hasNext) return null;
  return (
    <button type="button" className="btn-secondary w-full" onClick={onClick} disabled={loading}>
      {loading ? "Carregando…" : "Carregar mais"}
    </button>
  );
}

/** "Atualizado em": mostra a última sincronização com as fontes oficiais (RNF03). */
export function UpdatedAt({ job = "sync_votes" }: { job?: string }) {
  const { data } = useDataStatus();
  const ts = data?.jobs[job];
  if (!ts) return null;
  return (
    <p className="text-xs muted">
      Dados oficiais atualizados {relativeTime(ts)} · sincronização diária às 03h
    </p>
  );
}
