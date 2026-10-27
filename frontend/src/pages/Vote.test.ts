import { describe, expect, it } from "vitest";

import { placar } from "./Vote";

describe("placar da votação", () => {
  it("mostra as categorias básicas e só as do Senado que existirem", () => {
    expect(placar({ sim: 40 })).toEqual(["sim", "nao", "abstencao", "obstrucao", "ausente"]);
    expect(placar({ sim: 40, justificada: 6, secreto: 0 })).toEqual([
      "sim", "nao", "abstencao", "obstrucao", "ausente", "justificada",
    ]);
  });
});
