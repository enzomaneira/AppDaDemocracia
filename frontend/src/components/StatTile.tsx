import type { ReactNode } from "react";

import { compareToAverage } from "../lib/format";

interface Props {
  label: string;
  value: number | null;
  avg: number | null;
  format: (v: number | null) => string;
  hint?: string;
  action?: ReactNode;
}

/** Métrica + média da casa. Sem cores de "bom/ruim": o app não julga, só contextualiza. */
export function StatTile({ label, value, avg, format, hint, action }: Props) {
  const cmp = compareToAverage(value, avg);
  return (
    <div className="card flex flex-col gap-1">
      <span className="text-sm muted">{label}</span>
      <span className="text-2xl font-bold tabular-nums">{format(value)}</span>
      <span className="text-xs muted">
        Média da casa: <span className="tabular-nums">{format(avg)}</span>
        {cmp && <> · {cmp}</>}
      </span>
      {hint && <span className="text-xs muted">{hint}</span>}
      {action}
    </div>
  );
}
