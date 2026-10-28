import { useState } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { useMySurvey, useSurvey, useSurveyMutations } from "../api/hooks";
import { useAuth } from "../auth/AuthContext";
import { ErrorBox, Loading } from "../components/States";
import { SurveyForm } from "../components/SurveyForm";

/** Pesquisa opcional: logo após o cadastro, pelo cartão no feed ou pela Conta. */
export default function SurveyPage() {
  const { loggedIn } = useAuth();
  const [params] = useSearchParams();
  const next = params.get("next") || "/";
  const nav = useNavigate();
  const def = useSurvey();
  const mine = useMySurvey(loggedIn);
  const { answer, dismiss } = useSurveyMutations();
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");

  if (!loggedIn) return <Navigate to="/entrar" replace state={{ next: "/pesquisa" }} />;
  if (def.isLoading || mine.isLoading) return <Loading />;
  if (def.error || !def.data || mine.error || !mine.data) return <ErrorBox error={def.error ?? mine.error} />;

  const editing = !!mine.data.completed_at;

  if (done) {
    return (
      <section className="card flex flex-col items-center gap-3 py-8 text-center" role="status">
        <p className="text-4xl" aria-hidden="true">
          ✓
        </p>
        <h1 className="text-2xl font-bold">Obrigado!</h1>
        <p className="muted">Suas respostas ajudam a decidir o que vamos construir primeiro no app.</p>
        <p className="text-sm muted">Você pode mudar as respostas quando quiser em Conta.</p>
        <Link to={next} className="btn-primary">
          Continuar
        </Link>
      </section>
    );
  }

  async function submit(answers: Record<string, string[] | string>) {
    setError("");
    try {
      await answer.mutateAsync(answers);
      setDone(true);
      window.scrollTo({ top: 0, behavior: "smooth" });
    } catch (e) {
      setError(e instanceof Error ? e.message : "Não foi possível enviar. Tente de novo.");
    }
  }

  async function later() {
    try {
      await dismiss.mutateAsync(mine.data?.remind ?? false);
    } finally {
      nav(next, { replace: true });
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <header className="flex flex-col gap-2">
        <p className="text-sm font-semibold uppercase tracking-wide text-marca">Pesquisa · 2 minutos</p>
        <h1 className="text-2xl font-bold">{editing ? "Suas respostas" : "Ajude a construir o app"}</h1>
        <p className="muted">
          Queremos entender o que faria você acompanhar mais a política. As respostas são analisadas de forma agregada
          e ajudam a decidir o que construir primeiro. Todas as perguntas são opcionais, e a pesquisa não pergunta
          partido nem voto.
        </p>
      </header>
      <SurveyForm
        questions={def.data.questions}
        initial={mine.data.answers}
        submitLabel={editing ? "Salvar respostas" : "Enviar respostas"}
        busy={answer.isPending}
        error={error}
        onSubmit={submit}
        secondary={
          !editing && (
            <button type="button" className="btn-secondary" onClick={later} disabled={dismiss.isPending}>
              Agora não
            </button>
          )
        }
      />
    </div>
  );
}
