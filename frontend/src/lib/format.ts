import type { VoteChoice } from "../api/types";

const brl = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const dateFmt = new Intl.DateTimeFormat("pt-BR", { day: "2-digit", month: "short", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat("pt-BR", {
  day: "2-digit",
  month: "short",
  hour: "2-digit",
  minute: "2-digit",
});

export const formatBRL = (v: number | string | null | undefined) => (v == null ? "—" : brl.format(Number(v)));
export const formatDate = (iso: string) => dateFmt.format(new Date(iso));
export const formatDateTime = (iso: string) => dateTimeFmt.format(new Date(iso));

export function formatPercent(v: number | null | undefined) {
  return v == null ? "—" : `${v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

export function formatNumber(v: number | null | undefined) {
  return v == null ? "—" : v.toLocaleString("pt-BR", { maximumFractionDigits: 1 });
}

export function relativeTime(iso: string, now = new Date()) {
  const diff = (now.getTime() - new Date(iso).getTime()) / 1000;
  const future = diff < 0;
  const s = Math.abs(diff);
  const fmt = (n: number, unit: string) => (future ? `em ${n} ${unit}` : `há ${n} ${unit}`);
  if (s < 60) return future ? "em instantes" : "agora";
  if (s < 3600) return fmt(Math.floor(s / 60), "min");
  if (s < 86400) return fmt(Math.floor(s / 3600), "h");
  if (s < 86400 * 7) {
    const d = Math.floor(s / 86400);
    return fmt(d, d === 1 ? "dia" : "dias");
  }
  return formatDate(iso);
}

export const VOTE_LABEL: Record<VoteChoice, string> = {
  sim: "Sim",
  nao: "Não",
  abstencao: "Abstenção",
  obstrucao: "Obstrução",
  ausente: "Ausente",
  art17: "Presidindo a sessão",
  secreto: "Voto secreto",
  presente: "Presente, não votou",
  justificada: "Ausência justificada",
};

export const houseLabel = (h: string) => (h === "senado" ? "Senado" : "Câmara");
export const roleLabel = (h: string) => (h === "senado" ? "Senador(a)" : "Deputado(a) federal");

export function billLabel(b: { type: string; number: number | null; year: number | null } | null) {
  if (!b) return null;
  return b.number && b.year ? `${b.type} ${b.number}/${b.year}` : b.type;
}

/** Diferença em relação à média da casa, em texto neutro (sem juízo de valor). */
export function compareToAverage(value: number | null, avg: number | null) {
  if (value == null || avg == null || avg === 0) return null;
  const pct = ((value - avg) / avg) * 100;
  if (Math.abs(pct) < 1) return "igual à média da casa";
  const n = Math.abs(pct).toLocaleString("pt-BR", { maximumFractionDigits: 0 });
  return pct > 0 ? `${n}% acima da média da casa` : `${n}% abaixo da média da casa`;
}

export const BILL_TYPE_LABEL: Record<string, string> = {
  PL: "Projeto de lei",
  PLP: "Projeto de lei complementar",
  PEC: "Proposta de emenda à Constituição",
  PDL: "Projeto de decreto legislativo",
  PRC: "Projeto de resolução",
  PRS: "Projeto de resolução",
};
