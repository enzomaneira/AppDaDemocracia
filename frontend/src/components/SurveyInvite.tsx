import { Link } from "react-router-dom";

import { useMySurvey, useSurveyMutations } from "../api/hooks";

/**
 * Convite discreto no feed: aparece para quem nunca respondeu nem dispensou, e uma única vez
 * como lembrete alguns dias depois do "Agora não" (a regra fica no backend).
 */
export function SurveyInvite() {
  const mine = useMySurvey(true);
  const { dismiss } = useSurveyMutations();
  const s = mine.data;
  if (!s || !(s.prompt || s.remind)) return null;

  return (
    <aside className="card flex flex-col gap-3 border-marca/40" aria-label="Convite para a pesquisa">
      <div>
        <p className="font-semibold">Ajude a construir o app · 2 minutos</p>
        <p className="text-sm muted">
          Conte o que faria você acompanhar mais a política. As respostas ajudam a decidir o que vem primeiro.
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <Link to="/pesquisa" className="btn-primary min-h-9">
          Responder
        </Link>
        <button
          type="button"
          className="btn-secondary min-h-9"
          disabled={dismiss.isPending}
          onClick={() => dismiss.mutate(s.remind)}
        >
          Agora não
        </button>
      </div>
    </aside>
  );
}
