/**
 * Selo de novidades: o que entrou no feed desde a última visita.
 * A data fica só no navegador (localStorage); não é notificação e nada vai para o servidor.
 */

const KEY = "dem.visit";

export interface Visit {
  /** Corte do selo nesta visita: o que aconteceu depois disso é novo. `null` na primeira visita. */
  since: string | null;
  /** Última vez em que o Início foi aberto. */
  seen: string;
}

/** A pessoa saiu e voltou (visita nova) ou ainda é a mesma visita? */
export function visitEnded(lastSeen: Date, now: Date): boolean {
  // Mais de 30 minutos sem abrir o Início conta como visita nova.
  return now.getTime() - lastSeen.getTime() > 30 * 60_000;
}

/** Na mesma visita o corte fica parado, para o selo não sumir ao recarregar a página. */
export function resolveVisit(stored: Visit | null, now: Date): Visit {
  const seen = now.toISOString();
  if (!stored) return { since: null, seen };
  if (visitEnded(new Date(stored.seen), now)) return { since: stored.seen, seen };
  return { since: stored.since, seen };
}

function read(): Visit | null {
  try {
    const v = JSON.parse(localStorage.getItem(KEY) ?? "null") as Visit | null;
    return v && typeof v.seen === "string" && !Number.isNaN(Date.parse(v.seen)) ? v : null;
  } catch {
    return null;
  }
}

/** Registra a abertura do Início e devolve o corte do selo (`null`: nada a marcar). */
export function beginVisit(now = new Date()): Date | null {
  const visit = resolveVisit(read(), now);
  try {
    localStorage.setItem(KEY, JSON.stringify(visit));
  } catch {
    // Navegação privada ou armazenamento bloqueado: o app segue sem o selo.
  }
  return visit.since ? new Date(visit.since) : null;
}

export const isNew = (occurredAt: string, since: Date | null) =>
  since !== null && new Date(occurredAt).getTime() > since.getTime();

const dayStart = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();

/** "desde ontem", "desde hoje às 09:30" ou "desde 12/11". */
export function sinceLabel(since: Date, now = new Date()): string {
  const days = Math.round((dayStart(now) - dayStart(since)) / 86_400_000);
  if (days <= 0) {
    return `desde hoje às ${since.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" })}`;
  }
  if (days === 1) return "desde ontem";
  return `desde ${since.toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" })}`;
}
