import { useState } from "react";
import { Link } from "react-router-dom";

import { useFollows, useNews } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { NewsList } from "../components/NewsList";
import { Empty, ErrorBox, LoadMore, Loading } from "../components/States";

export default function News() {
  const { loggedIn } = useAuth();
  const [politician, setPolitician] = useState("");
  const follows = useFollows(loggedIn);
  const news = useNews(politician, loggedIn);

  if (!loggedIn) {
    return (
      <Empty title="Notícias de quem você segue">
        <p className="mb-4">Entre para ver as notícias dos parlamentares que você acompanha.</p>
        <Link to="/entrar" className="btn-primary">
          Entrar
        </Link>
      </Empty>
    );
  }
  const items = news.data?.pages.flatMap((p) => p.items) ?? [];
  return (
    <div className="flex flex-col gap-4">
      <h1 className="text-2xl font-bold">Notícias</h1>
      <label className="flex flex-col gap-1">
        <span className="text-sm font-medium">Filtrar por político</span>
        <select className="input" value={politician} onChange={(e) => setPolitician(e.target.value)}>
          <option value="">Todos que eu sigo</option>
          {follows.data?.map((f) => (
            <option key={f.politician.id} value={f.politician.id}>
              {f.politician.name}
            </option>
          ))}
        </select>
      </label>
      <p className="text-xs muted">
        Mostramos só título, trecho e link para o veículo. Uma notícia é vinculada quando cita o nome do parlamentar e o
        contexto (cargo, partido ou UF) confere.
      </p>
      {news.isLoading ? (
        <Loading />
      ) : news.error ? (
        <ErrorBox error={news.error} />
      ) : items.length === 0 ? (
        <Empty title="Nenhuma notícia por enquanto" />
      ) : (
        <NewsList items={items} showPoliticians />
      )}
      <LoadMore hasNext={news.hasNextPage} loading={news.isFetchingNextPage} onClick={() => news.fetchNextPage()} />
    </div>
  );
}
