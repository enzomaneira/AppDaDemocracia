import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, hasSession, onAuthChange, setTokens } from "../api/client";
import { useMe } from "../api/hooks";
import type { TokenOut, User } from "../api/types";

interface AuthState {
  user: User | null;
  loggedIn: boolean;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (data: { email: string; name: string; password: string; uf?: string; accept_terms: boolean }) => Promise<void>;
  logout: () => Promise<void>;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient();
  const [loggedIn, setLoggedIn] = useState(hasSession());
  useEffect(() => {
    const off = onAuthChange(setLoggedIn);
    return () => {
      off();
    };
  }, []);
  const me = useMe(loggedIn);

  const login = useCallback(
    async (email: string, password: string) => {
      setTokens(await api<TokenOut>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }));
      await qc.invalidateQueries();
    },
    [qc],
  );

  const register = useCallback<AuthState["register"]>(
    async (data) => {
      setTokens(await api<TokenOut>("/auth/register", { method: "POST", body: JSON.stringify(data) }));
      await qc.invalidateQueries();
    },
    [qc],
  );

  const logout = useCallback(async () => {
    try {
      const refresh_token = localStorage.getItem("dem.refresh");
      if (refresh_token) await api("/auth/logout", { method: "POST", body: JSON.stringify({ refresh_token }) });
    } catch {
      /* sair localmente mesmo se a API falhar */
    }
    setTokens(null);
    qc.clear();
  }, [qc]);

  const value = useMemo(
    () => ({
      user: me.data ?? null,
      loggedIn,
      loading: loggedIn && me.isLoading,
      login,
      register,
      logout,
    }),
    [me.data, me.isLoading, loggedIn, login, register, logout],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useAuth fora do AuthProvider");
  return ctx;
}
