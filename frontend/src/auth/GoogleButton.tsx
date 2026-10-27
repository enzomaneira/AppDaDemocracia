import { useEffect, useRef, useState } from "react";

// Google Identity Services: o botão e a janela de login são do próprio Google; o app só
// recebe um ID token assinado (nenhuma senha passa por aqui).
const GIS_SRC = "https://accounts.google.com/gsi/client";
export const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? "";

interface GoogleAccountsId {
  initialize(config: {
    client_id: string;
    callback: (resp: { credential?: string }) => void;
    ux_mode?: "popup" | "redirect";
    cancel_on_tap_outside?: boolean;
  }): void;
  renderButton(el: HTMLElement, options: Record<string, string | number>): void;
}

declare global {
  interface Window {
    google?: { accounts: { id: GoogleAccountsId } };
  }
}

let loading: Promise<void> | null = null;

function loadGis(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  loading ??= new Promise((resolve, reject) => {
    const s = document.createElement("script");
    s.src = GIS_SRC;
    s.async = true;
    s.defer = true;
    s.onload = () => resolve();
    s.onerror = () => {
      loading = null;
      reject(new Error("Não foi possível carregar o login do Google"));
    };
    document.head.appendChild(s);
  });
  return loading;
}

export function GoogleButton({
  onCredential,
  text = "continue_with",
}: {
  onCredential: (idToken: string) => void;
  text?: "signin_with" | "signup_with" | "continue_with";
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [error, setError] = useState("");
  // O callback do Google é registrado uma vez; a ref mantém sempre a versão atual.
  const cb = useRef(onCredential);
  cb.current = onCredential;

  useEffect(() => {
    if (!GOOGLE_CLIENT_ID) return;
    let cancelled = false;
    loadGis()
      .then(() => {
        const gid = window.google?.accounts.id;
        if (cancelled || !gid || !ref.current) return;
        gid.initialize({
          client_id: GOOGLE_CLIENT_ID,
          ux_mode: "popup",
          cancel_on_tap_outside: true,
          callback: (resp) => resp.credential && cb.current(resp.credential),
        });
        gid.renderButton(ref.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          shape: "pill",
          text,
          locale: "pt-BR",
          width: Math.min(ref.current.offsetWidth || 320, 400),
        });
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [text]);

  if (!GOOGLE_CLIENT_ID) return null;
  return (
    <div className="flex flex-col gap-1">
      <div ref={ref} className="flex min-h-11 w-full justify-center" />
      {error && (
        <p role="alert" className="text-sm text-voto-nao">
          {error}
        </p>
      )}
    </div>
  );
}
