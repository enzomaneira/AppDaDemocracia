import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { api } from "../api/client";
import { useBulkFollow, useFollows, useMySurvey, useSearch } from "../api/hooks";
import type { House, PoliticianSummary } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PoliticianCard } from "../components/PoliticianCard";
import { ErrorBox, Loading } from "../components/States";
import { UFS } from "../lib/ufs";

// A maior bancada (SP) tem 70 deputados: uma página de 100 traz a casa inteira da UF.
const WHOLE_STATE = 100;

/** RF02: escolher a UF e seguir os parlamentares do estado em um toque. */
export default function Onboarding() {
  const { user, loggedIn } = useAuth();
  const qc = useQueryClient();
  const [uf, setUf] = useState(user?.uf ?? "");
  const follows = useFollows(loggedIn);
  const survey = useMySurvey(loggedIn);
  // Próximo passo: a pesquisa (opcional, com "Agora não") para quem nunca respondeu.
  const after = survey.data?.prompt ? "/pesquisa?next=/" : "/";

  if (!loggedIn) return <Navigate to="/entrar" replace />;

  async function choose(value: string) {
    setUf(value);
    if (value) {
      await api("/me", { method: "PATCH", body: JSON.stringify({ uf: value }) });
      qc.invalidateQueries({ queryKey: ["me"] });
    }
  }

  const followed = new Set(follows.data?.map((f) => f.politician.id));

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Quem representa você?</h1>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Seu estado</span>
        <select className="input" value={uf} onChange={(e) => choose(e.target.value)}>
          <option value="">Escolha a UF</option>
          {UFS.map(([s, n]) => (
            <option key={s} value={s}>
              {n}
            </option>
          ))}
        </select>
      </label>
      {uf && (
        <>
          <Group title={`Senadores por ${uf}`} uf={uf} house="senado" followed={followed} />
          <Group title={`Deputados federais por ${uf}`} uf={uf} house="camara" followed={followed} />
        </>
      )}
      <Link to={after} className="btn-primary sticky bottom-20 sm:bottom-4">
        {followed.size ? `Continuar (${followed.size} seguidos)` : "Pular por agora"}
      </Link>
    </div>
  );
}

/** Uma casa da UF, com o botão que segue todos de uma vez. */
function Group({ title, uf, house, followed }: { title: string; uf: string; house: House; followed: Set<string> }) {
  const res = useSearch({ uf, house, limit: WHOLE_STATE });
  const bulk = useBulkFollow();

  if (res.isLoading) return <Loading />;
  if (res.error) return <ErrorBox error={res.error} />;
  const items: PoliticianSummary[] = res.data?.pages.flatMap((p) => p.items) ?? [];
  if (!items.length) return null;
  const pending = items.filter((p) => !followed.has(p.id)).length;

  return (
    <section>
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {pending > 0 ? (
          <button
            type="button"
            className="btn-secondary min-h-9 px-3"
            disabled={bulk.isPending}
            onClick={() => bulk.mutate({ uf, house })}
          >
            {pending === items.length ? `Seguir todos (${items.length})` : `Seguir os outros ${pending}`}
          </button>
        ) : (
          <span className="text-sm muted">Seguindo todos</span>
        )}
      </div>
      {bulk.error && <ErrorBox error={bulk.error} />}
      <ul className="flex flex-col gap-2">
        {items.map((p) => (
          <PoliticianCard key={p.id} p={p} following={followed.has(p.id)} />
        ))}
      </ul>
    </section>
  );
}
