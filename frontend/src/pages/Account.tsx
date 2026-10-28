import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";

import { api, setTokens } from "../api/client";
import { useFollowMutation, useFollows } from "../api/hooks";
import type { Follow } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Avatar } from "../components/PoliticianCard";
import { Loading } from "../components/States";

export default function Account() {
  const { user, loggedIn, loading, logout } = useAuth();
  const follows = useFollows(loggedIn);
  const nav = useNavigate();
  const qc = useQueryClient();
  const [confirming, setConfirming] = useState(false);

  if (!loggedIn) return <Navigate to="/entrar" replace state={{ next: "/conta" }} />;
  if (loading || !user) return <Loading />;

  async function exportData() {
    const data = await api("/me/export");
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "meus-dados-app-da-democracia.json";
    a.click();
    URL.revokeObjectURL(a.href);
  }

  async function deleteAccount() {
    await api("/me", { method: "DELETE" });
    setTokens(null);
    qc.clear();
    nav("/", { replace: true });
  }

  return (
    <div className="flex flex-col gap-6">
      <section className="card flex flex-col gap-1">
        <h1 className="text-xl font-bold">{user.name}</h1>
        <p className="text-sm muted">{user.email}</p>
        {user.uf && <p className="text-sm muted">Estado: {user.uf}</p>}
        <div className="mt-3 flex flex-wrap gap-2">
          <Link to="/comecar" className="btn-secondary">
            Mudar estado
          </Link>
          {user.is_admin && (
            <Link to="/admin/lista" className="btn-secondary">
              Resultados da lista de espera
            </Link>
          )}
          <button className="btn-secondary" onClick={() => logout().then(() => nav("/"))}>
            Sair
          </button>
        </div>
      </section>

      <section>
        <h2 className="mb-1 text-lg font-semibold">Seguindo e notificações</h2>
        <p className="mb-3 text-sm muted">
          Escolha o que quer acompanhar de cada parlamentar. Os avisos por push e e-mail chegam numa próxima versão.
        </p>
        {follows.isLoading ? (
          <Loading />
        ) : follows.data?.length ? (
          <ul className="flex flex-col gap-2">
            {follows.data.map((f) => (
              <FollowRow key={f.politician.id} f={f} />
            ))}
          </ul>
        ) : (
          <p className="text-sm muted">Você ainda não segue ninguém.</p>
        )}
      </section>

      <section className="card flex flex-col gap-3">
        <h2 className="font-semibold">Seus dados (LGPD)</h2>
        <p className="text-sm muted">
          Guardamos só nome, e-mail, estado e quem você segue. Quem você segue pode revelar opinião política, por isso
          essa lista é tratada como dado sensível e nunca é pública.
        </p>
        <div className="flex flex-wrap gap-2">
          <button className="btn-secondary" onClick={exportData}>
            Exportar meus dados
          </button>
          {!confirming ? (
            <button className="btn-secondary text-voto-nao" onClick={() => setConfirming(true)}>
              Excluir conta
            </button>
          ) : (
            <span className="flex flex-wrap items-center gap-2" role="alert">
              <span className="text-sm">Excluir conta e seguidos de forma definitiva?</span>
              <button className="btn bg-voto-nao text-white" onClick={deleteAccount}>
                Sim, excluir
              </button>
              <button className="btn-secondary" onClick={() => setConfirming(false)}>
                Cancelar
              </button>
            </span>
          )}
        </div>
      </section>
    </div>
  );
}

function FollowRow({ f }: { f: Follow }) {
  const m = useFollowMutation();
  const toggle = (key: "notify_votes" | "notify_agenda" | "notify_news") =>
    m.mutate({
      id: f.politician.id,
      follow: true,
      prefs: { notify_votes: f.notify_votes, notify_agenda: f.notify_agenda, notify_news: f.notify_news, [key]: !f[key] },
    });
  return (
    <li className="card flex flex-col gap-3 sm:flex-row sm:items-center">
      <Link to={`/politico/${f.politician.slug}`} className="flex flex-1 items-center gap-3">
        <Avatar p={f.politician} size={40} />
        <span className="font-semibold">{f.politician.name}</span>
      </Link>
      <fieldset className="flex flex-wrap gap-3 text-sm" disabled={m.isPending}>
        <legend className="sr-only">Notificações de {f.politician.name}</legend>
        {(
          [
            ["notify_votes", "Votos"],
            ["notify_agenda", "Agenda"],
            ["notify_news", "Notícias"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex items-center gap-1.5">
            <input type="checkbox" className="size-4" checked={f[key]} onChange={() => toggle(key)} />
            {label}
          </label>
        ))}
        <button className="text-voto-nao underline" onClick={() => m.mutate({ id: f.politician.id, follow: false })}>
          Deixar de seguir
        </button>
      </fieldset>
    </li>
  );
}
