import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { useFollows, useSearch, type SearchFilters } from "../api/hooks";
import type { House } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { PoliticianCard } from "../components/PoliticianCard";
import { Empty, ErrorBox, LoadMore, Loading } from "../components/States";
import { UFS } from "../lib/ufs";

export default function Search() {
  const [params, setParams] = useSearchParams();
  const [q, setQ] = useState(params.get("q") ?? "");
  const filters: SearchFilters = {
    q: params.get("q") ?? "",
    uf: params.get("uf") ?? "",
    party: params.get("party") ?? "",
    house: (params.get("house") as House | null) ?? "",
  };

  // Busca enquanto digita, com pequeno atraso para não disparar uma requisição por tecla.
  useEffect(() => {
    const t = setTimeout(() => update("q", q.trim()), 300);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q]);

  function update(key: string, value: string) {
    setParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        if (value) next.set(key, value);
        else next.delete(key);
        return next;
      },
      { replace: true },
    );
  }

  const { loggedIn } = useAuth();
  const follows = useFollows(loggedIn);
  const followed = new Set(follows.data?.map((f) => f.politician.id));
  const res = useSearch(filters);
  const items = res.data?.pages.flatMap((p) => p.items) ?? [];

  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Buscar parlamentares</h1>
      <form role="search" className="flex flex-col gap-3" onSubmit={(e) => e.preventDefault()}>
        <label className="flex flex-col gap-1">
          <span className="text-sm font-medium">Nome</span>
          <input
            className="input"
            type="search"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ex.: Maria, Silva…"
            autoComplete="off"
          />
        </label>
        <div className="grid grid-cols-3 gap-2">
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Casa</span>
            <select className="input" value={filters.house} onChange={(e) => update("house", e.target.value)}>
              <option value="">Todas</option>
              <option value="camara">Câmara</option>
              <option value="senado">Senado</option>
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">UF</span>
            <select className="input" value={filters.uf} onChange={(e) => update("uf", e.target.value)}>
              <option value="">Todas</option>
              {UFS.map(([sigla, nome]) => (
                <option key={sigla} value={sigla}>
                  {sigla} – {nome}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-sm font-medium">Partido</span>
            <input
              className="input uppercase"
              value={filters.party}
              onChange={(e) => update("party", e.target.value.trim())}
              placeholder="Sigla"
              maxLength={20}
            />
          </label>
        </div>
      </form>

      {res.isLoading ? (
        <Loading />
      ) : res.error ? (
        <ErrorBox error={res.error} />
      ) : items.length === 0 ? (
        <Empty title="Nenhum parlamentar encontrado">Tente outro nome ou remova algum filtro.</Empty>
      ) : (
        <ul className="flex flex-col gap-2" aria-live="polite">
          {items.map((p) => (
            <PoliticianCard key={p.id} p={p} following={followed.has(p.id)} />
          ))}
        </ul>
      )}
      <LoadMore hasNext={res.hasNextPage} loading={res.isFetchingNextPage} onClick={() => res.fetchNextPage()} />
    </div>
  );
}
