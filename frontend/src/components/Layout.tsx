import { Link, NavLink, Outlet } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

const NAV = [
  { to: "/", label: "Feed", icon: "⌂", end: true },
  { to: "/buscar", label: "Buscar", icon: "⌕" },
  { to: "/noticias", label: "Notícias", icon: "☰" },
  { to: "/conta", label: "Conta", icon: "◉" },
];

export function Layout() {
  const { user, loggedIn } = useAuth();
  return (
    <div className="mx-auto flex min-h-dvh max-w-3xl flex-col">
      <a href="#conteudo" className="sr-only focus:not-sr-only focus:p-2">
        Pular para o conteúdo
      </a>
      <header className="sticky top-0 z-10 flex items-center justify-between border-b border-slate-200 bg-white/90 px-4 py-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/90">
        <Link to="/" className="flex items-center gap-2 font-bold">
          <img src="/icon.svg" alt="" width={28} height={28} />
          App da Democracia
        </Link>
        <nav aria-label="Principal" className="hidden gap-1 sm:flex">
          {NAV.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium ${isActive ? "bg-marca/10 text-marca" : "hover:bg-slate-100 dark:hover:bg-slate-800"}`
              }
            >
              {n.label}
            </NavLink>
          ))}
        </nav>
        {!loggedIn && (
          <Link to="/entrar" className="btn-primary min-h-9 sm:hidden">
            Entrar
          </Link>
        )}
        {user && <span className="hidden text-sm muted md:inline">Olá, {user.name.split(" ")[0]}</span>}
      </header>

      <main id="conteudo" className="flex-1 px-4 pb-24 pt-4 sm:pb-8">
        <Outlet />
      </main>

      <footer className="hidden px-4 pb-6 text-xs muted sm:block">
        Dados oficiais da Câmara dos Deputados e do Senado Federal ·{" "}
        <Link to="/como-calculamos" className="underline">
          Como calculamos
        </Link>{" "}
        ·{" "}
        <Link to="/privacidade" className="underline">
          Privacidade
        </Link>
      </footer>

      {/* Navegação inferior no celular (mobile first) */}
      <nav
        aria-label="Principal"
        className="fixed inset-x-0 bottom-0 z-10 grid grid-cols-4 border-t border-slate-200 bg-white pb-[env(safe-area-inset-bottom)] sm:hidden dark:border-slate-800 dark:bg-slate-950"
      >
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.end}
            className={({ isActive }) =>
              `flex min-h-14 flex-col items-center justify-center text-xs font-medium ${isActive ? "text-marca" : "muted"}`
            }
          >
            <span aria-hidden="true" className="text-lg leading-none">
              {n.icon}
            </span>
            {n.label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}
