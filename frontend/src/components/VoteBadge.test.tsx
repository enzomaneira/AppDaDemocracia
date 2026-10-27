import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StatTile } from "./StatTile";
import { VoteBadge } from "./VoteBadge";

describe("VoteBadge", () => {
  it.each([
    ["sim", "Sim"],
    ["nao", "Não"],
    ["abstencao", "Abstenção"],
    ["obstrucao", "Obstrução"],
    ["ausente", "Ausente"],
  ] as const)("mostra o voto %s com texto, não só cor", (choice, label) => {
    render(<VoteBadge choice={choice} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });
});

describe("StatTile", () => {
  it("sempre mostra a média da casa ao lado da métrica", () => {
    render(<StatTile label="Presença" value={80} avg={90} format={(v) => `${v}%`} />);
    expect(screen.getByText("80%")).toBeInTheDocument();
    expect(screen.getByText("90%")).toBeInTheDocument();
    expect(screen.getByText(/abaixo da média da casa/)).toBeInTheDocument();
  });
});
