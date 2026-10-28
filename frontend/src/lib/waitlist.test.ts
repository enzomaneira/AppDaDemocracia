import { describe, expect, it } from "vitest";

import type { SurveyQuestion } from "../api/types";
import { answeredCount, atLimit, isChosen, sourceFromUrl, toggleChoice } from "./waitlist";

const single: SurveyQuestion = {
  id: "frequencia",
  text: "?",
  kind: "single",
  max: null,
  max_length: null,
  options: [
    { id: "nunca", label: "Nunca" },
    { id: "diario", label: "Todo dia" },
  ],
};
const multi: SurveyQuestion = { ...single, id: "temas", kind: "multi", max: 2 };

describe("toggleChoice", () => {
  it("escolha única troca e desmarca", () => {
    let a = toggleChoice({}, single, "nunca");
    expect(a).toEqual({ frequencia: "nunca" });
    a = toggleChoice(a, single, "diario");
    expect(a).toEqual({ frequencia: "diario" });
    expect(toggleChoice(a, single, "diario")).toEqual({});
  });

  it("múltipla escolha respeita o máximo", () => {
    let a = toggleChoice({}, multi, "saude");
    a = toggleChoice(a, multi, "educacao");
    expect(atLimit(a, multi)).toBe(true);
    expect(toggleChoice(a, multi, "agro")).toBe(a); // no limite, ignora
    a = toggleChoice(a, multi, "saude");
    expect(a).toEqual({ temas: ["educacao"] });
    expect(isChosen(a, multi, "educacao")).toBe(true);
    expect(toggleChoice(a, multi, "educacao")).toEqual({});
  });
});

describe("helpers", () => {
  it("conta perguntas respondidas, sem a aberta", () => {
    const text: SurveyQuestion = { ...single, id: "aberta", kind: "text", options: [] };
    expect(answeredCount({ frequencia: "nunca", temas: ["saude"], aberta: "oi" }, [single, multi, text])).toBe(2);
  });

  it("lê a origem da visita com segurança", () => {
    expect(sourceFromUrl("?ref=Instagram")).toBe("instagram");
    expect(sourceFromUrl("?utm_source=news<script>")).toBe("newsscript");
    expect(sourceFromUrl("")).toBeUndefined();
  });
});
