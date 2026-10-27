import type { VoteChoice } from "../api/types";
import { VOTE_LABEL } from "../lib/format";

const STYLE: Record<VoteChoice, { cls: string; icon: string }> = {
  sim: { cls: "bg-voto-sim/12 text-voto-sim ring-voto-sim/40", icon: "✓" },
  nao: { cls: "bg-voto-nao/12 text-voto-nao ring-voto-nao/40", icon: "✕" },
  abstencao: { cls: "bg-voto-abstencao/15 text-voto-abstencao ring-voto-abstencao/40", icon: "○" },
  obstrucao: { cls: "bg-voto-obstrucao/12 text-voto-obstrucao ring-voto-obstrucao/40", icon: "⊘" },
  ausente: { cls: "bg-ausente/12 text-ausente ring-ausente/40", icon: "–" },
  art17: { cls: "bg-ausente/12 text-ausente ring-ausente/40", icon: "§" },
};

/** Voto com ícone + texto: a cor nunca é o único sinal (WCAG). */
export function VoteBadge({ choice, size = "md" }: { choice: VoteChoice; size?: "sm" | "md" }) {
  const s = STYLE[choice] ?? STYLE.ausente;
  const pad = size === "sm" ? "px-2 py-0.5 text-xs" : "px-2.5 py-1 text-sm";
  return (
    <span className={`inline-flex items-center gap-1 rounded-full font-semibold ring-1 ring-inset ${pad} ${s.cls}`}>
      <span aria-hidden="true">{s.icon}</span>
      {VOTE_LABEL[choice] ?? choice}
    </span>
  );
}
