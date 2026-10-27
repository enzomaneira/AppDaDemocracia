import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate } from "react-router-dom";

import { api } from "../api/client";
import { useFollows, useSearch } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { PoliticianCard } from "../components/PoliticianCard";
import { ErrorBox, LoadMore, Loading } from "../components/States";
import { UFS } from "../lib/ufs";

/** RF02: escolher a UF e seguir os parlamentares do estado em um toque. */
export default function Onboarding() {
  const { user, loggedIn } = useAuth();
  const qc = useQueryClient();
  const [uf, setUf] = useState(user?.uf ?? "");
  const follows = useFollows(loggedIn);
  const res = useSearch({ uf: uf || undefined });

  if (!loggedIn) return <Navigate to="/entrar" replace />;

  async function choose(value: string) {
    setUf(value);
    if (value) {
      await api("/me", { method: "PATCH", body: JSON.stringify({ uf: value }) });
      qc.invalidateQueries({ queryKey: ["me"] });
    }
  }

  const followed = new Set(follows.data?.map((f) => f.politician.id));
  const items = uf ? (res.data?.pages.flatMap((p) => p.items) ?? []) : [];
  const senators = items.filter((p) => p.house === "senado");
  const deputies = items.filter((p) => p.house === "camara");

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
      {uf &&
        (res.isLoading ? (
          <Loading />
        ) : res.error ? (
          <ErrorBox error={res.error} />
        ) : (
          <>
            <Group title={`Senadores por ${uf}`} items={senators} followed={followed} />
            <Group title={`Deputados federais por ${uf}`} items={deputies} followed={followed} />
            <LoadMore hasNext={res.hasNextPage} loading={res.isFetchingNextPage} onClick={() => res.fetchNextPage()} />
          </>
        ))}
      <Link to="/" className="btn-primary sticky bottom-20 sm:bottom-4">
        {followed.size ? `Ver meu feed (${followed.size} seguidos)` : "Pular por agora"}
      </Link>
    </div>
  );
}

function Group({
  title,
  items,
  followed,
}: {
  title: string;
  items: ReturnType<typeof useSearch>["data"] extends infer D ? (D extends { pages: { items: infer I }[] } ? I : never) : never;
  followed: Set<string>;
}) {
  if (!items.length) return null;
  return (
    <section>
      <h2 className="mb-2 font-semibold">{title}</h2>
      <ul className="flex flex-col gap-2">
        {items.map((p) => (
          <PoliticianCard key={p.id} p={p} following={followed.has(p.id)} />
        ))}
      </ul>
    </section>
  );
}
