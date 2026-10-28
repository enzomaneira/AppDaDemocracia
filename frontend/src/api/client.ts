import type { TokenOut } from "./types";

export const API_URL = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");
const REFRESH_KEY = "dem.refresh";

// Access token só em memória; o refresh token fica no armazenamento local para manter a sessão.
let accessToken: string | null = null;
let refreshing: Promise<boolean> | null = null;
const listeners = new Set<(loggedIn: boolean) => void>();

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function readRefresh(): string | null {
  try {
    return localStorage.getItem(REFRESH_KEY);
  } catch {
    return null;
  }
}

export function setTokens(t: TokenOut | null) {
  accessToken = t?.access_token ?? null;
  try {
    if (t) localStorage.setItem(REFRESH_KEY, t.refresh_token);
    else localStorage.removeItem(REFRESH_KEY);
  } catch {
    /* modo privado: a sessão dura só esta aba */
  }
  listeners.forEach((fn) => fn(!!t));
}

export function hasSession() {
  return !!accessToken || !!readRefresh();
}

export function onAuthChange(fn: (loggedIn: boolean) => void) {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

async function refresh(): Promise<boolean> {
  const token = readRefresh();
  if (!token) return false;
  refreshing ??= (async () => {
    try {
      const r = await fetch(`${API_URL}/api/v1/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: token }),
      });
      if (!r.ok) {
        setTokens(null);
        return false;
      }
      setTokens(await r.json());
      return true;
    } catch {
      return false;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

export function toQuery(params: Record<string, string | number | boolean | null | undefined>) {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  }
  const s = q.toString();
  return s ? `?${s}` : "";
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  if (!accessToken && readRefresh()) await refresh();
  const headers = new Headers(init.headers);
  if (init.body) headers.set("Content-Type", "application/json");
  if (accessToken) headers.set("Authorization", `Bearer ${accessToken}`);

  const r = await fetch(`${API_URL}/api/v1${path}`, { ...init, headers });
  if (r.status === 401 && retry && readRefresh() && (await refresh())) {
    return api<T>(path, init, false);
  }
  if (!r.ok) {
    let detail = r.statusText;
    try {
      const body = await r.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* sem corpo JSON */
    }
    throw new ApiError(r.status, detail || "Erro ao falar com o servidor");
  }
  return (r.status === 204 ? undefined : await r.json()) as T;
}

/** Baixa um arquivo autenticado (ex.: CSV do admin) e entrega ao navegador para salvar. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  if (!accessToken && readRefresh()) await refresh();
  const r = await fetch(`${API_URL}/api/v1${path}`, {
    headers: accessToken ? { Authorization: `Bearer ${accessToken}` } : {},
  });
  if (!r.ok) throw new ApiError(r.status, "Não foi possível baixar o arquivo");
  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
