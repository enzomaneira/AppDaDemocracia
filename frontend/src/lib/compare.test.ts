import { describe, expect, it } from "vitest";

import { agreementText, barShares, rankByName } from "./compare";

describe("barShares", () => {
  it("é proporcional ao maior valor", () => {
    expect(barShares(80, 40)).toEqual([100, 50]);
    expect(barShares(25, 100)).toEqual([25, 100]);
    expect(barShares(10, 10)).toEqual([100, 100]);
  });

  it("lida com falta de dado e zeros", () => {
    expect(barShares(null, 50)).toEqual([0, 100]);
    expect(barShares(0, 0)).toEqual([0, 0]);
    expect(barShares(null, null)).toEqual([0, 0]);
  });
});

describe("agreementText", () => {
  it("descreve a concordância de forma neutra", () => {
    expect(agreementText(3, 1)).toBe("Votaram igual em 2 de 3 votações em comum · divergiram em 1.");
    expect(agreementText(1, 0)).toBe("Votaram igual em 1 de 1 votação em comum · divergiram em 0.");
    expect(agreementText(0, 0)).toMatch(/Nenhuma votação/);
  });
});

describe("rankByName", () => {
  it("põe primeiro quem começa com o termo, ignorando acentos", () => {
    const items = ["Alexandre Guimarães", "Josimar Maranhãozinho", "Junio Amaral", "Mara Gabrilli", "Damares Alves"].map(
      (name) => ({ name }),
    );
    expect(rankByName(items, "mara").map((i) => i.name)).toEqual([
      "Mara Gabrilli", // começa com o termo
      "Josimar Maranhãozinho", // uma palavra começa com o termo
      // contêm o termo no meio (gui-MARA-es, a-MARA-l): mantêm a ordem original
      "Alexandre Guimarães",
      "Junio Amaral",
      "Damares Alves", // não contém no nome parlamentar (só bateu no nome civil)
    ]);
    expect(rankByName([{ name: "Sérgio Moro" }], "serg")[0].name).toBe("Sérgio Moro");
  });
});
