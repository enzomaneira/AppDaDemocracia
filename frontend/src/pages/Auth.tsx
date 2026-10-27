import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { GOOGLE_CLIENT_ID, GoogleButton } from "../auth/GoogleButton";
import { UFS } from "../lib/ufs";

/** Botão do Google + aviso de termos (o aviso vem antes do clique: o aceite é informado). */
function GoogleLogin({ next, text }: { next: string; text: "signin_with" | "signup_with" }) {
  const { loginWithGoogle } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState("");
  if (!GOOGLE_CLIENT_ID) return null;

  async function onCredential(idToken: string) {
    setError("");
    try {
      await loginWithGoogle(idToken);
      nav(next, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível entrar com o Google.");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <GoogleButton onCredential={onCredential} text={text} />
      <p className="text-center text-xs muted">
        Ao continuar com o Google, você aceita os termos de uso e a{" "}
        <Link to="/privacidade" className="underline">
          política de privacidade
        </Link>
        . Usamos só seu nome e e-mail.
      </p>
      {error && (
        <p role="alert" className="text-sm text-voto-nao">
          {error}
        </p>
      )}
      <div className="flex items-center gap-3 text-xs muted" aria-hidden="true">
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
        ou com e-mail
        <span className="h-px flex-1 bg-slate-200 dark:bg-slate-800" />
      </div>
    </div>
  );
}

function Field(props: { label: string; children: React.ReactNode }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-sm font-medium">{props.label}</span>
      {props.children}
    </label>
  );
}

export function Login() {
  const { login } = useAuth();
  const nav = useNavigate();
  const next = (useLocation().state as { next?: string } | null)?.next ?? "/";
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await login(String(f.get("email")), String(f.get("password")));
      nav(next, { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível entrar.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto flex max-w-sm flex-col gap-4 py-6">
      <h1 className="text-2xl font-bold">Entrar</h1>
      <GoogleLogin next={next} text="signin_with" />
      <Field label="E-mail">
        <input className="input" name="email" type="email" autoComplete="email" required />
      </Field>
      <Field label="Senha">
        <input className="input" name="password" type="password" autoComplete="current-password" required />
      </Field>
      {error && (
        <p role="alert" className="text-sm text-voto-nao">
          {error}
        </p>
      )}
      <button className="btn-primary" disabled={busy}>
        {busy ? "Entrando…" : "Entrar"}
      </button>
      <p className="text-sm muted">
        Não tem conta?{" "}
        <Link to="/cadastro" className="text-marca underline">
          Criar conta
        </Link>
      </p>
    </form>
  );
}

export function Register() {
  const { register } = useAuth();
  const nav = useNavigate();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    setBusy(true);
    setError("");
    try {
      await register({
        name: String(f.get("name")),
        email: String(f.get("email")),
        password: String(f.get("password")),
        uf: String(f.get("uf") || "") || undefined,
        accept_terms: f.get("terms") === "on",
      });
      nav("/comecar", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Não foi possível criar a conta.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mx-auto flex max-w-sm flex-col gap-4 py-6">
      <h1 className="text-2xl font-bold">Criar conta</h1>
      <GoogleLogin next="/comecar" text="signup_with" />
      <p className="text-sm muted">
        Coletamos só nome, e-mail e quem você segue. Sua lista de seguidos nunca é pública.
      </p>
      <Field label="Nome">
        <input className="input" name="name" autoComplete="name" required maxLength={120} />
      </Field>
      <Field label="E-mail">
        <input className="input" name="email" type="email" autoComplete="email" required />
      </Field>
      <Field label="Senha (mínimo 8 caracteres)">
        <input className="input" name="password" type="password" autoComplete="new-password" minLength={8} required />
      </Field>
      <Field label="Seu estado (opcional)">
        <select className="input" name="uf" defaultValue="">
          <option value="">Escolher depois</option>
          {UFS.map(([s, n]) => (
            <option key={s} value={s}>
              {n}
            </option>
          ))}
        </select>
      </Field>
      <label className="flex items-start gap-2 text-sm">
        <input type="checkbox" name="terms" required className="mt-1 size-4" />
        <span>
          Li e aceito os termos de uso e a{" "}
          <Link to="/privacidade" className="text-marca underline">
            política de privacidade
          </Link>
          .
        </span>
      </label>
      {error && (
        <p role="alert" className="text-sm text-voto-nao">
          {error}
        </p>
      )}
      <button className="btn-primary" disabled={busy}>
        {busy ? "Criando…" : "Criar conta"}
      </button>
      <p className="text-sm muted">
        Já tem conta?{" "}
        <Link to="/entrar" className="text-marca underline">
          Entrar
        </Link>
      </p>
    </form>
  );
}
