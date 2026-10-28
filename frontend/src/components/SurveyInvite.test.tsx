import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import type { MySurvey } from "../api/types";
import { SurveyInvite } from "./SurveyInvite";

function renderWith(state: Partial<MySurvey>) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
  qc.setQueryData(["my-survey"], { answers: {}, completed_at: null, prompt: false, remind: false, ...state });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter>
        <SurveyInvite />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SurveyInvite", () => {
  it("convida na primeira vez, com opção de dispensar", () => {
    renderWith({ prompt: true });
    expect(screen.getByRole("link", { name: "Responder" })).toHaveAttribute("href", "/pesquisa");
    expect(screen.getByRole("button", { name: "Agora não" })).toBeInTheDocument();
  });

  it("aparece de novo só como lembrete", () => {
    renderWith({ remind: true });
    expect(screen.getByText(/Ajude a construir o app/)).toBeInTheDocument();
  });

  it("some para quem já respondeu ou dispensou", () => {
    const { container } = renderWith({ completed_at: "2026-11-01T12:00:00Z" });
    expect(container).toBeEmptyDOMElement();
  });
});
