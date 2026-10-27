import { describe, expect, it } from "vitest";

import { toQuery } from "../api/client";
import { billLabel, compareToAverage, formatPercent, relativeTime } from "./format";

describe("format", () => {
  it("formata percentual em pt-BR", () => {
    expect(formatPercent(75.5)).toBe("75,5%");
    expect(formatPercent(null)).toBe("—");
  });

  it("compara com a média da casa em texto neutro", () => {
    expect(compareToAverage(110, 100)).toBe("10% acima da média da casa");
    expect(compareToAverage(90, 100)).toBe("10% abaixo da média da casa");
    expect(compareToAverage(100.2, 100)).toBe("igual à média da casa");
    expect(compareToAverage(null, 100)).toBeNull();
  });

  it("monta rótulo de proposição", () => {
    expect(billLabel({ type: "PL", number: 10, year: 2026 })).toBe("PL 10/2026");
    expect(billLabel({ type: "MPV", number: null, year: null })).toBe("MPV");
  });

  it("tempo relativo", () => {
    const now = new Date("2026-10-27T12:00:00Z");
    expect(relativeTime("2026-10-27T11:30:00Z", now)).toBe("há 30 min");
    expect(relativeTime("2026-10-25T12:00:00Z", now)).toBe("há 2 dias");
    expect(relativeTime("2026-10-27T15:00:00Z", now)).toBe("em 3 h");
  });

  it("monta query string ignorando vazios", () => {
    expect(toQuery({ q: "ana", uf: "", house: undefined, limit: 2 })).toBe("?q=ana&limit=2");
    expect(toQuery({})).toBe("");
  });
});
