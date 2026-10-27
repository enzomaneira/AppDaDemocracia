/**
 * Larguras das barras lado a lado (0–100), proporcionais ao maior dos dois valores.
 * Sem dado de um lado, a barra dele fica vazia; com os dois zerados, nenhuma aparece.
 */
export function barShares(a: number | null, b: number | null): [number, number] {
  const max = Math.max(a ?? 0, b ?? 0);
  if (max <= 0) return [0, 0];
  const pct = (v: number | null) => Math.round(((v ?? 0) / max) * 100);
  return [pct(a), pct(b)];
}

const fold = (s: string) =>
  s
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .trim();

/**
 * Ordena resultados de busca pelo que a pessoa provavelmente quis: nome que começa com o
 * termo, depois alguma palavra do nome que começa com ele, depois o resto (ex.: só o nome
 * civil bate). A API devolve em ordem alfabética, o que esconde "Mara Gabrilli" atrás de
 * "Maranhãozinho" e "Amaral" quando se digita "Mara".
 */
export function rankByName<T extends { name: string }>(items: T[], query: string): T[] {
  const q = fold(query);
  const rank = (name: string) => {
    const n = fold(name);
    if (n.startsWith(q)) return 0;
    if (n.split(/\s+/).some((w) => w.startsWith(q))) return 1;
    return n.includes(q) ? 2 : 3;
  };
  return items
    .map((item, i) => ({ item, i, r: rank(item.name) }))
    .sort((x, y) => x.r - y.r || x.i - y.i)
    .map((x) => x.item);
}

/** Texto do resumo de concordância, sem juízo de valor. */
export function agreementText(common: number, divergent: number) {
  if (common === 0) return "Nenhuma votação nominal em comum com voto público no período.";
  const same = common - divergent;
  const v = (n: number) => (n === 1 ? "votação" : "votações");
  return `Votaram igual em ${same} de ${common} ${v(common)} em comum · divergiram em ${divergent}.`;
}
