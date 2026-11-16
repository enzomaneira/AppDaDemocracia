import { beforeEach, describe, expect, it } from "vitest";

import { beginVisit, isNew, resolveVisit, sinceLabel, visitEnded } from "./lastVisit";

const at = (iso: string) => new Date(iso);

describe("resolveVisit", () => {
  it("na primeira visita não marca nada", () => {
    expect(resolveVisit(null, at("2026-11-15T12:00:00Z"))).toEqual({
      since: null,
      seen: "2026-11-15T12:00:00.000Z",
    });
  });

  it("ao voltar depois de um dia, o corte é a visita anterior", () => {
    const v = resolveVisit({ since: null, seen: "2026-11-14T12:00:00.000Z" }, at("2026-11-15T12:00:00Z"));
    expect(v).toEqual({ since: "2026-11-14T12:00:00.000Z", seen: "2026-11-15T12:00:00.000Z" });
  });

  it("recarregar em seguida mantém o corte", () => {
    const stored = { since: "2026-11-14T12:00:00.000Z", seen: "2026-11-15T12:00:00.000Z" };
    expect(resolveVisit(stored, at("2026-11-15T12:00:05Z")).since).toBe("2026-11-14T12:00:00.000Z");
  });
});

describe("visitEnded", () => {
  it("vira visita nova depois de 30 minutos sem abrir o Início", () => {
    const seen = at("2026-11-15T12:00:00Z");
    expect(visitEnded(seen, at("2026-11-15T12:30:00Z"))).toBe(false);
    expect(visitEnded(seen, at("2026-11-15T12:30:01Z"))).toBe(true);
  });
});

describe("beginVisit", () => {
  beforeEach(() => localStorage.clear());

  it("guarda a visita no navegador e devolve o corte na volta", () => {
    expect(beginVisit(at("2026-11-14T12:00:00Z"))).toBeNull();
    expect(beginVisit(at("2026-11-15T12:00:00Z"))).toEqual(at("2026-11-14T12:00:00Z"));
  });

  it("ignora valor inválido no armazenamento", () => {
    localStorage.setItem("dem.visit", "{lixo");
    expect(beginVisit(at("2026-11-15T12:00:00Z"))).toBeNull();
  });
});

describe("isNew", () => {
  it("só marca o que aconteceu depois do corte", () => {
    const since = at("2026-11-14T12:00:00Z");
    expect(isNew("2026-11-14T12:00:01Z", since)).toBe(true);
    expect(isNew("2026-11-14T12:00:00Z", since)).toBe(false);
    expect(isNew("2026-11-15T12:00:00Z", null)).toBe(false);
  });
});

describe("sinceLabel", () => {
  const now = new Date(2026, 10, 15, 10, 0);

  it("fala em ontem, hoje ou na data", () => {
    expect(sinceLabel(new Date(2026, 10, 14, 23, 0), now)).toBe("desde ontem");
    expect(sinceLabel(new Date(2026, 10, 15, 9, 30), now)).toBe("desde hoje às 09:30");
    expect(sinceLabel(new Date(2026, 10, 12, 8, 0), now)).toBe("desde 12/11");
  });
});
