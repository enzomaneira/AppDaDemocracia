import { Link } from "react-router-dom";

import type { PoliticianSummary } from "../api/types";
import { roleLabel } from "../lib/format";
import { FollowButton } from "./FollowButton";

export function Avatar({ p, size = 48 }: { p: Pick<PoliticianSummary, "photo_url" | "name">; size?: number }) {
  const initials = p.name
    .split(" ")
    .slice(0, 2)
    .map((w) => w[0])
    .join("");
  return p.photo_url ? (
    <img
      src={p.photo_url}
      alt={`Foto de ${p.name}`}
      width={size}
      height={size}
      loading="lazy"
      className="shrink-0 rounded-full bg-slate-200 object-cover dark:bg-slate-800"
      style={{ width: size, height: size }}
    />
  ) : (
    <span
      aria-hidden="true"
      className="grid shrink-0 place-items-center rounded-full bg-slate-200 font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300"
      style={{ width: size, height: size }}
    >
      {initials}
    </span>
  );
}

export function PoliticianLine({ p }: { p: PoliticianSummary }) {
  return (
    <span className="text-sm muted">
      {roleLabel(p.house)} · {p.party ?? "sem partido"}-{p.uf}
      {!p.in_office && " · fora do exercício"}
    </span>
  );
}

export function PoliticianCard({ p, following }: { p: PoliticianSummary; following?: boolean }) {
  return (
    <li className="card flex items-center gap-3">
      <Avatar p={p} />
      <Link to={`/politico/${p.slug}`} className="min-w-0 flex-1">
        <span className="block truncate font-semibold hover:underline">{p.name}</span>
        <PoliticianLine p={p} />
      </Link>
      {following !== undefined && <FollowButton id={p.id} following={following} compact name={p.name} />}
    </li>
  );
}
