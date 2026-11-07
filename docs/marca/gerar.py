"""Gera o manual de marca do Plenário como SVGs importáveis no Figma (texto e vetores editáveis)."""
import json
import sys
import textwrap
from pathlib import Path
from xml.sax.saxutils import escape

SAIDA = Path(sys.argv[1])
(SAIDA / "paginas").mkdir(parents=True, exist_ok=True)
(SAIDA / "logo").mkdir(parents=True, exist_ok=True)

W, H = 1440, 1024
M = 96  # margem

C = {
    "areia": "#F7F2EA",
    "papel": "#FFFDF9",
    "areia2": "#F1EBE1",
    "linha": "#E6DDD0",
    "tinta": "#1E2A33",
    "suave": "#66707A",
    "cupula": "#173A63",
    "azulejo": "#1D4E89",
    "planalto": "#8FC1E3",
    "petroleo": "#0F766E",
    "terracota": "#D4603F",
    "ocre": "#B7801A",
    "lilas": "#7B5EA7",
    "chip_azul": "#E3ECF6",
}
DISPLAY = "Bricolage Grotesque"
TEXTO = "Figtree"
MONO = "IBM Plex Mono"

TOTAL = 9


# ---------- utilitários ----------

def t(x, y, s, size=20, fam=TEXTO, w=400, fill=C["tinta"], anchor="start", ls=0, extra=""):
    return (
        f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{w}" '
        f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{ls}" {extra}>{escape(s)}</text>'
    )


def bloco(x, y, s, largura, size=20, fam=TEXTO, w=400, fill=C["tinta"], lh=1.45, fator=0.5):
    """Texto com quebra de linha aproximada pela largura (Figma mantém cada linha como texto editável)."""
    maxc = max(10, int(largura / (size * fator)))
    linhas = []
    for par in s.split("\n"):
        linhas += textwrap.wrap(par, maxc) or [""]
    tsp = "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else size * lh:.1f}">{escape(l)}</tspan>' for i, l in enumerate(linhas)
    )
    svg = f'<text x="{x}" y="{y}" font-family="{fam}" font-size="{size}" font-weight="{w}" fill="{fill}">{tsp}</text>'
    return svg, y + size * lh * (len(linhas) - 1)


def rect(x, y, w, h, fill, r=0, stroke=None, sw=1, extra=""):
    s = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{s} {extra}/>'


def simbolo(x, y, tam, claro=False):
    """Cúpulas do Congresso dentro de um balão de conversa (viewBox 44)."""
    balao, cup, torre = (C["areia"], C["azulejo"], C["cupula"]) if claro else (C["azulejo"], C["areia"], C["planalto"])
    k = tam / 44
    return f'''<g transform="translate({x} {y}) scale({k:.4f})">
  <path d="M9 4h26a7 7 0 0 1 7 7v15a7 7 0 0 1-7 7H20l-9 8v-8H9a7 7 0 0 1-7-7V11a7 7 0 0 1 7-7z" fill="{balao}"/>
  <path d="M7 21 Q12.5 28.5 18 21 Z" fill="{cup}"/>
  <path d="M26 22.5 Q31.5 14.5 37 22.5 Z" fill="{cup}"/>
  <rect x="19.4" y="10" width="1.9" height="13" rx=".6" fill="{torre}"/>
  <rect x="22.6" y="10" width="1.9" height="13" rx=".6" fill="{torre}"/>
  <rect x="6" y="24.2" width="32" height="2" rx="1" fill="{cup}"/>
</g>'''


def logo(x, y, tam, claro=False):
    cor = C["areia"] if claro else C["tinta"]
    return simbolo(x, y, tam, claro) + t(x + tam * 1.18, y + tam * 0.66, "plenário", size=tam * 0.68, fam=DISPLAY, w=800, fill=cor, ls=-tam * 0.012)


def azulejos(x, y, w, h, opac=0.14, id_="az", r=0):
    return f'''<defs>
  <pattern id="{id_}" width="64" height="64" patternUnits="userSpaceOnUse" x="{x}" y="{y}">
    <path d="M0 32A32 32 0 0 1 32 0v32z" fill="{C["areia"]}"/>
    <path d="M64 32A32 32 0 0 0 32 0v32z" fill="none" stroke="{C["areia"]}" stroke-width="3"/>
    <circle cx="16" cy="48" r="8" fill="{C["planalto"]}"/>
    <path d="M32 64a32 32 0 0 1 32-32v32z" fill="{C["planalto"]}"/>
  </pattern>
</defs>
<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="url(#{id_})" opacity="{opac}"/>'''


def pagina(n, secao, titulo, corpo, fundo=C["areia"], escuro=False):
    tinta = C["areia"] if escuro else C["tinta"]
    suave = "#F7F2EAB3" if escuro else C["suave"]
    topo = (
        t(M, 64, "MANUAL DE MARCA · PLENÁRIO", 13, MONO, 500, suave, ls=1.4)
        + t(W - M, 64, f"{n:02d} / {TOTAL:02d}", 13, MONO, 500, suave, "end", ls=1.4)
    )
    cab = ""
    if titulo:
        cab = t(M, 150, secao.upper(), 14, MONO, 500, C["planalto"] if escuro else C["azulejo"], ls=1.6) + t(
            M, 214, titulo, 56, DISPLAY, 800, tinta, ls=-1.2
        )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<title>{n:02d} {escape(secao)}</title>
<rect width="{W}" height="{H}" fill="{fundo}"/>
{corpo}
{topo}
{cab}
</svg>'''


paginas = []

# ---------- 01 Capa ----------
corpo = azulejos(0, 0, W, H, 0.13, "az1")
corpo += simbolo(M, 300, 168, claro=True)
corpo += t(M, 640, "plenário", 168, DISPLAY, 800, C["areia"], ls=-5)
corpo += t(M, 720, "Manual de marca", 40, DISPLAY, 600, C["planalto"])
corpo += t(M, 900, "O Congresso, em linguagem de gente.", 26, TEXTO, 500, C["areia"])
corpo += t(M, 940, "Identidade Brasília acolhedora · versão 1.0 · outubro de 2026", 18, TEXTO, 400, "#F7F2EAB3")
paginas.append(("01-capa", pagina(1, "Capa", None, corpo, C["cupula"], escuro=True)))

# ---------- 02 Essência ----------
corpo = ""
p, _ = bloco(M, 300, "O Plenário aproxima as pessoas da vida política. Mostra, com dados oficiais e em linguagem simples, como votam, se trabalham e quanto gastam os políticos que cada um elegeu.", 620, 26, TEXTO, 500, C["tinta"], 1.4)
corpo += p
corpo += t(M, 560, "PROPÓSITO", 13, MONO, 500, C["suave"], ls=1.4)
p, _ = bloco(M, 596, "Que acompanhar a política seja tão natural quanto acompanhar o próprio time.", 560, 22, DISPLAY, 700, C["azulejo"], 1.35, 0.52)
corpo += p
# personalidade
corpo += t(800, 280, "PERSONALIDADE", 13, MONO, 500, C["suave"], ls=1.4)
pers = [
    ("Confiável", "Mostra a fonte de cada número."),
    ("Apartidária", "Trata todos os partidos do mesmo jeito."),
    ("Acolhedora", "Explica sem julgar quem sabe pouco."),
    ("Brasileira", "Nasce dos símbolos e do modernismo de Brasília."),
    ("Direta", "Frases curtas, sem juridiquês."),
]
y = 320
for nome, d in pers:
    corpo += rect(800, y, 544, 92, C["papel"], 20, C["linha"])
    corpo += t(828, y + 40, nome, 24, DISPLAY, 800)
    corpo += t(828, y + 70, d, 17, TEXTO, 400, C["suave"])
    y += 108
corpo += t(M, 900, "É · próxima, clara, séria quando precisa", 18, TEXTO, 600, C["petroleo"])
corpo += t(M, 932, "Não é · torcida, sarcasmo, opinião sobre candidatos", 18, TEXTO, 600, C["terracota"])
paginas.append(("02-essencia", pagina(2, "Essência", "Quem é o Plenário", corpo)))

# ---------- 03 Logo ----------
corpo = rect(M, 270, 744, 440, C["papel"], 28, C["linha"])
corpo += logo(M + 120, 420, 120)
corpo += rect(880, 270, 464, 440, C["cupula"], 28)
corpo += logo(880 + 64, 445, 76, claro=True)
corpo += t(M, 750, "Assinatura principal", 20, TEXTO, 700)
corpo += t(M, 778, "Símbolo + nome em minúsculas, Bricolage Grotesque ExtraBold.", 17, TEXTO, 400, C["suave"])
corpo += t(880, 750, "Versão sobre fundo escuro", 20, TEXTO, 700)
corpo += t(880, 778, "Balão em areia, cúpulas em azul.", 17, TEXTO, 400, C["suave"])
# anatomia
corpo += t(M, 850, "ANATOMIA DO SÍMBOLO", 13, MONO, 500, C["suave"], ls=1.4)
corpo += simbolo(M, 870, 110)
anat = [
    ("Balão de conversa", "a marca fala com as pessoas"),
    ("Cúpula côncava", "a Câmara dos Deputados"),
    ("Cúpula convexa", "o Senado Federal"),
    ("Torres gêmeas", "o Congresso Nacional"),
]
x = 260
for nome, d in anat:
    corpo += t(x, 905, nome, 18, TEXTO, 700)
    corpo += t(x, 932, d, 16, TEXTO, 400, C["suave"])
    x += 280
paginas.append(("03-logo", pagina(3, "Logo", "Assinatura e símbolo", corpo)))

# ---------- 04 Regras do logo ----------
corpo = ""
# área de proteção
corpo += t(M, 290, "ÁREA DE PROTEÇÃO", 13, MONO, 500, C["suave"], ls=1.4)
corpo += rect(M, 310, 560, 300, C["papel"], 24, C["linha"])
corpo += rect(M + 70, 380, 420, 160, "none", 0, C["planalto"], 2, 'stroke-dasharray="8 6"')
corpo += logo(M + 110, 420, 80)
corpo += t(M + 70, 372, "x", 16, MONO, 500, C["azulejo"])
p, _ = bloco(M, 650, "Deixe em volta do logo um espaço livre igual à altura do balão (x). Nada de texto, borda ou imagem dentro dessa área.", 560, 18, TEXTO, 400, C["suave"])
corpo += p
# tamanho mínimo
corpo += t(M, 780, "TAMANHO MÍNIMO", 13, MONO, 500, C["suave"], ls=1.4)
corpo += logo(M, 800, 32)
corpo += t(M + 200, 826, "Assinatura: 96 px de largura", 17, TEXTO, 500)
corpo += simbolo(M, 860, 24)
corpo += t(M + 200, 880, "Símbolo sozinho: 24 px (ícone do app e favicon)", 17, TEXTO, 500)
# usos incorretos
corpo += t(760, 290, "NÃO FAÇA", 13, MONO, 500, C["terracota"], ls=1.4)
erros = [
    ("Mudar as cores", f'<g opacity="1">{simbolo(0, 0, 70).replace(C["azulejo"], "#D7262E")}</g>'),
    ("Distorcer", f'<g transform="scale(1.6 0.8)">{simbolo(0, 10, 60)}</g>'),
    ("Usar sobre fundo poluído", ""),
    ("Contornar ou sombrear", f'<g style="filter:none">{simbolo(0, 0, 70)}</g>'),
]
cx = [760, 1056]
cy = [310, 590]
for i, (rot, g) in enumerate(erros):
    x, y = cx[i % 2], cy[i // 2]
    corpo += rect(x, y, 280, 230, C["papel"], 20, C["linha"])
    if rot == "Usar sobre fundo poluído":
        corpo += rect(x + 20, y + 56, 200, 110, C["terracota"], 12) + rect(x + 50, y + 76, 150, 70, C["planalto"], 35) + rect(x + 90, y + 60, 70, 100, C["ocre"], 8)
        corpo += simbolo(x + 85, y + 76, 64)
    elif rot == "Contornar ou sombrear":
        corpo += f'<g transform="translate({x + 105} {y + 55})"><rect x="-6" y="-6" width="82" height="82" rx="12" fill="none" stroke="{C["tinta"]}" stroke-width="4"/>{simbolo(0, 0, 70)}</g>'
    else:
        corpo += f'<g transform="translate({x + 100} {y + 55})">{g}</g>'
    corpo += f'<path d="M{x + 236} {y + 22} l20 20 m0 -20 l-20 20" stroke="{C["terracota"]}" stroke-width="4" stroke-linecap="round"/>'
    corpo += t(x + 24, y + 200, rot, 17, TEXTO, 600)
paginas.append(("04-regras-logo", pagina(4, "Logo", "Como usar o logo", corpo)))

# ---------- 05 Cores ----------
corpo = ""
principais = [
    ("Areia", "areia", "Fundo principal", "247 242 234"),
    ("Cúpula", "cupula", "Cabeçalhos e fundos de marca", "23 58 99"),
    ("Azulejo", "azulejo", "Botões, links e destaques", "29 78 137"),
    ("Planalto", "planalto", "Apoio sobre fundos escuros", "143 193 227"),
    ("Tinta", "tinta", "Texto", "30 42 51"),
]
x = M
for nome, k, uso, rgb in principais:
    claro = k in ("areia", "planalto")
    corpo += rect(x, 270, 232, 260, C[k], 24, C["linha"] if claro else None)
    cor_txt = C["tinta"] if claro else C["areia"]
    corpo += t(x + 22, 316, nome, 26, DISPLAY, 800, cor_txt)
    corpo += t(x + 22, 470, C[k], 16, MONO, 500, cor_txt)
    corpo += t(x + 22, 496, f"RGB {rgb}", 14, MONO, 400, cor_txt)
    p, _ = bloco(x, 562, uso, 220, 16, TEXTO, 400, C["suave"])
    corpo += p
    x += 252
corpo += t(M, 680, "CORES DE VOTO", 13, MONO, 500, C["suave"], ls=1.4)
voto = [("Sim", "petroleo"), ("Não", "terracota"), ("Abstenção", "ocre"), ("Obstrução", "lilas")]
x = M
for nome, k in voto:
    corpo += rect(x, 700, 160, 64, C[k], 32)
    corpo += t(x + 80, 741, nome.upper(), 17, TEXTO, 800, "#FFFFFF", "middle", 1)
    corpo += t(x, 790, C[k], 14, MONO, 500, C["suave"])
    x += 176
p, _ = bloco(864, 704, "Regra de neutralidade: nenhuma cor associada a partidos (vermelho, verde e amarelo juntos) é cor principal da marca. Sim e Não sempre aparecem com o nome escrito, nunca só pela cor.", 480, 18, TEXTO, 500, C["tinta"], 1.45)
corpo += rect(836, 670, 508, 160, C["papel"], 20, C["linha"]) + p
corpo += t(M, 900, "Proporção sugerida em uma tela: 60% areia · 20% cúpula · 12% azulejo · 8% cores de voto e apoio", 18, TEXTO, 500, C["suave"])
corpo += rect(M, 920, 1248, 20, C["areia2"], 10)
corpo += rect(M, 920, 749, 20, C["areia2"], 10, C["linha"]) + rect(M + 749, 920, 250, 20, C["cupula"]) + rect(M + 999, 920, 150, 20, C["azulejo"]) + rect(M + 1149, 920, 99, 20, C["petroleo"], 0)
paginas.append(("05-cores", pagina(5, "Cores", "Paleta", corpo)))

# ---------- 06 Tipografia ----------
corpo = ""
corpo += rect(M, 270, 600, 420, C["papel"], 24, C["linha"])
corpo += t(M + 40, 330, "TÍTULOS", 13, MONO, 500, C["azulejo"], ls=1.4)
corpo += t(M + 40, 470, "Aa", 150, DISPLAY, 800, C["tinta"], ls=-4)
corpo += t(M + 40, 540, "Bricolage Grotesque", 32, DISPLAY, 800)
corpo += t(M + 40, 580, "ExtraBold 800 · SemiBold 600", 18, TEXTO, 400, C["suave"])
corpo += t(M + 40, 650, "Google Fonts · licença livre (OFL)", 15, MONO, 500, C["suave"])
corpo += rect(744, 270, 600, 420, C["papel"], 24, C["linha"])
corpo += t(784, 330, "TEXTO", 13, MONO, 500, C["azulejo"], ls=1.4)
corpo += t(784, 470, "Aa", 150, TEXTO, 600, C["tinta"])
corpo += t(784, 540, "Figtree", 32, TEXTO, 700)
corpo += t(784, 580, "Regular 400 · Semibold 600 · Bold 700", 18, TEXTO, 400, C["suave"])
corpo += t(784, 650, "Google Fonts · licença livre (OFL)", 15, MONO, 500, C["suave"])
corpo += t(M, 760, "ESCALA", 13, MONO, 500, C["suave"], ls=1.4)
escala = [
    (56, DISPLAY, 800, "Título de página", "56 / 60"),
    (36, DISPLAY, 800, "Título de seção", "36 / 40"),
    (24, DISPLAY, 700, "Título de cartão", "24 / 30"),
    (17, TEXTO, 400, "Texto corrido: frases curtas, em linguagem do dia a dia.", "17 / 26"),
    (13, TEXTO, 700, "ETIQUETA · CÂMARA · SENADO", "13 / 16"),
]
y = 800
for size, fam, w, ex, med in escala:
    corpo += t(M, y + size * 0.4, ex, size, fam, w, ls=-0.02 * size if fam == DISPLAY else (1 if size == 13 else 0))
    corpo += t(W - M, y + size * 0.4, med, 14, MONO, 500, C["suave"], "end")
    y += max(size * 1.05, 34)
paginas.append(("06-tipografia", pagina(6, "Tipografia", "Fontes e escala", corpo)))

# ---------- 07 Elementos gráficos ----------
corpo = rect(M, 270, 620, 460, C["cupula"], 28) + azulejos(M, 270, 620, 460, 0.35, "az7", 28)
corpo += t(M, 770, "Padrão de azulejos", 20, TEXTO, 700)
p, _ = bloco(M, 800, "Homenagem a Athos Bulcão. Quartos de círculo em módulos de 64 px, em areia e planalto sobre cúpula. Use só em fundos de marca: cabeçalhos, capas e topo da landing page. Opacidade entre 12% e 16%.", 620, 17, TEXTO, 400, C["suave"])
corpo += p
# módulo ampliado
corpo += t(780, 290, "MÓDULO", 13, MONO, 500, C["suave"], ls=1.4)
corpo += f'''<g transform="translate(780 310) scale(3)">
  <rect width="64" height="64" fill="{C["cupula"]}"/>
  <path d="M0 32A32 32 0 0 1 32 0v32z" fill="{C["areia"]}"/>
  <path d="M64 32A32 32 0 0 0 32 0v32z" fill="none" stroke="{C["areia"]}" stroke-width="3"/>
  <circle cx="16" cy="48" r="8" fill="{C["planalto"]}"/>
  <path d="M32 64a32 32 0 0 1 32-32v32z" fill="{C["planalto"]}"/>
</g>'''
corpo += t(1010, 290, "FORMAS", 13, MONO, 500, C["suave"], ls=1.4)
corpo += rect(1010, 310, 300, 56, C["azulejo"], 28) + t(1160, 345, "Botão em pílula", 18, TEXTO, 700, "#FFFFFF", "middle")
corpo += rect(1010, 386, 130, 34, C["chip_azul"], 17) + t(1075, 409, "CÂMARA", 13, TEXTO, 700, C["azulejo"], "middle", 1)
corpo += rect(1150, 386, 120, 34, "#EEE7F6", 17) + t(1210, 409, "SENADO", 13, TEXTO, 700, C["lilas"], "middle", 1)
corpo += rect(1010, 440, 300, 150, C["papel"], 20, C["linha"]) + t(1030, 480, "Cartão", 20, DISPLAY, 800) + t(1030, 510, "cantos de 20 px, borda", 15, TEXTO, 400, C["suave"]) + t(1030, 532, "de 1 px, sem sombra", 15, TEXTO, 400, C["suave"])
corpo += t(1010, 640, "Raios: 999 px (pílulas) · 20 px", 15, TEXTO, 500, C["suave"])
corpo += t(1010, 664, "(cartões) · 12 px (campos)", 15, TEXTO, 500, C["suave"])
paginas.append(("07-elementos", pagina(7, "Elementos gráficos", "Azulejos e formas", corpo)))

# ---------- 08 Tom de voz ----------
corpo = ""
p, _ = bloco(M, 290, "Falamos como um amigo bem informado: explica o que aconteceu, mostra a fonte e deixa a conclusão com a pessoa.", 1100, 26, TEXTO, 500, C["tinta"], 1.4)
corpo += p
pares = [
    ("“Deputada Fulana votou Sim. A proposta foi aprovada por 312 a 141.”", "“Fulana traiu o povo de novo!”"),
    ("“PEC é uma mudança na Constituição. Precisa de 3/5 dos votos.”", "“Proposta de Emenda Constitucional nos termos do art. 60.”"),
    ("“Esteve em 32 das 40 votações. Faltas podem ter justificativa.”", "“Ausente e preguiçoso: veja quem mais falta!”"),
]
corpo += t(M, 430, "FAÇA", 13, MONO, 500, C["petroleo"], ls=1.4)
corpo += t(744, 430, "EVITE", 13, MONO, 500, C["terracota"], ls=1.4)
y = 450
for bom, ruim in pares:
    corpo += rect(M, y, 620, 120, C["papel"], 20, C["linha"]) + rect(M, y, 6, 120, C["petroleo"], 3)
    p, _ = bloco(M + 32, y + 50, bom, 560, 19, TEXTO, 500, C["tinta"], 1.4)
    corpo += p
    corpo += rect(744, y, 600, 120, C["papel"], 20, C["linha"]) + rect(744, y, 6, 120, C["terracota"], 3)
    p, _ = bloco(776, y + 50, ruim, 540, 19, TEXTO, 500, C["suave"], 1.4)
    corpo += p
    y += 140
regras = "Frases curtas · voz ativa · sempre com a fonte · nunca adjetivar políticos · explicar sigla na primeira vez"
corpo += t(M, 920, regras, 18, TEXTO, 600, C["azulejo"])
paginas.append(("08-tom-de-voz", pagina(8, "Tom de voz", "Como o Plenário fala", corpo)))

# ---------- 09 Aplicações ----------
corpo = ""
# cartão de votação
cx, cy = M, 270
corpo += rect(cx, cy, 560, 280, C["papel"], 22, C["linha"])
corpo += rect(cx + 28, cy + 30, 96, 30, C["chip_azul"], 15) + t(cx + 76, cy + 51, "CÂMARA", 12, TEXTO, 700, C["azulejo"], "middle", 1)
corpo += t(cx + 140, cy + 52, "Reforma do ensino médio", 20, TEXTO, 700)
corpo += t(cx + 532, cy + 52, "ontem · 18:40", 15, TEXTO, 400, C["suave"], "end")
corpo += t(cx + 28, cy + 130, "312", 48, DISPLAY, 800, C["petroleo"]) + t(cx + 120, cy + 130, "SIM", 15, TEXTO, 800, C["petroleo"], ls=1)
corpo += t(cx + 532, cy + 130, "141", 48, DISPLAY, 800, C["terracota"], "end") + t(cx + 440, cy + 130, "NÃO", 15, TEXTO, 800, C["terracota"], "end", 1)
corpo += rect(cx + 230, cy + 100, 100, 30, "#0F766E1F", 15) + t(cx + 280, cy + 121, "Aprovada", 14, TEXTO, 700, C["petroleo"], "middle")
corpo += rect(cx + 28, cy + 160, 504, 10, C["areia2"], 5) + rect(cx + 28, cy + 160, 338, 10, C["petroleo"], 5) + rect(cx + 381, cy + 160, 151, 10, C["terracota"], 5)
corpo += rect(cx + 28, cy + 200, 56, 28, C["petroleo"], 14) + t(cx + 56, cy + 219, "SIM", 12, TEXTO, 800, "#FFFFFF", "middle", 1) + t(cx + 96, cy + 220, "Sua deputada", 16, TEXTO, 500)
corpo += rect(cx + 250, cy + 200, 56, 28, C["terracota"], 14) + t(cx + 278, cy + 219, "NÃO", 12, TEXTO, 800, "#FFFFFF", "middle", 1) + t(cx + 318, cy + 220, "Seu senador", 16, TEXTO, 500)
corpo += t(M, 590, "Cartão de votação no app", 18, TEXTO, 700)
corpo += t(M, 616, "Números ilustrativos.", 15, TEXTO, 400, C["suave"])
# cabeçalho do app
corpo += rect(M, 660, 560, 84, C["cupula"], 22) + azulejos(M, 660, 560, 84, 0.13, "az9b", 22)
corpo += logo(M + 28, 683, 40, claro=True) + t(M + 532, 711, "Congresso Nacional", 15, TEXTO, 400, "#F7F2EAB3", "end")
corpo += t(M, 784, "Cabeçalho do app", 18, TEXTO, 700)
# post 1080x1350 em escala 0.5 (540x675)
px, py = 760, 250
corpo += rect(px, py, 540, 675, C["cupula"], 0) + azulejos(px, py, 540, 675, 0.12, "az9")
corpo += rect(px + 40, py + 40, 120, 34, "#F7F2EA1F", 17) + t(px + 100, py + 63, "VOTAÇÃO", 13, TEXTO, 700, C["areia"], "middle", 1)
corpo += t(px + 40, py + 150, "O que mudou no", 40, DISPLAY, 800, C["areia"], ls=-1)
corpo += t(px + 40, py + 198, "ensino médio ontem", 40, DISPLAY, 800, C["areia"], ls=-1)
corpo += rect(px + 40, py + 250, 460, 220, C["papel"], 22)
corpo += t(px + 70, py + 340, "312", 64, DISPLAY, 800, C["petroleo"]) + t(px + 70, py + 372, "SIM", 15, TEXTO, 800, C["petroleo"], ls=1)
corpo += t(px + 470, py + 340, "141", 64, DISPLAY, 800, C["terracota"], "end") + t(px + 470, py + 372, "NÃO", 15, TEXTO, 800, C["terracota"], "end", 1)
corpo += rect(px + 70, py + 410, 400, 12, C["areia2"], 6) + rect(px + 70, py + 410, 268, 12, C["petroleo"], 6) + rect(px + 350, py + 410, 120, 12, C["terracota"], 6)
corpo += t(px + 40, py + 530, "Veja como votou quem você elegeu.", 20, TEXTO, 500, C["areia"])
corpo += logo(px + 40, py + 580, 40, claro=True)
corpo += t(px + 500, py + 612, "Fonte: Câmara dos Deputados", 13, TEXTO, 400, "#F7F2EAB3", "end")
corpo += t(px, 960, "Post para Instagram (1080 × 1350, mostrado a 50%)", 18, TEXTO, 700)
paginas.append(("09-aplicacoes", pagina(9, "Aplicações", "A marca em uso", corpo)))

for nome, svg in paginas:
    (SAIDA / "paginas" / f"{nome}.svg").write_text(svg, encoding="utf-8")


# ---------- Logos avulsos ----------
def logo_avulso(claro, com_nome):
    w = 360 if com_nome else 44
    fundo = f'<rect width="{w}" height="44" fill="{C["cupula"]}"/>' if claro else ""
    conteudo = logo(0, 0, 44, claro) if com_nome else simbolo(0, 0, 44, claro)
    if com_nome:
        w = 196
        fundo = f'<rect width="{w}" height="44" fill="{C["cupula"]}"/>' if claro else ""
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="44" viewBox="0 0 {w} 44">{fundo}{conteudo}</svg>'


for nome, claro, com_nome in [
    ("simbolo-azul", False, False),
    ("simbolo-areia", True, False),
    ("assinatura-azul", False, True),
    ("assinatura-areia", True, True),
]:
    (SAIDA / "logo" / f"{nome}.svg").write_text(logo_avulso(claro, com_nome), encoding="utf-8")

# ---------- Tokens (W3C Design Tokens / DTCG) ----------
cor = lambda v, d: {"$type": "color", "$value": v, "$description": d}
tokens = {
    "cor": {
        "areia": cor(C["areia"], "Fundo principal"),
        "papel": cor(C["papel"], "Superfície de cartões"),
        "areia-2": cor(C["areia2"], "Superfície secundária e trilhos"),
        "linha": cor(C["linha"], "Bordas"),
        "tinta": cor(C["tinta"], "Texto"),
        "suave": cor(C["suave"], "Texto secundário"),
        "cupula": cor(C["cupula"], "Cabeçalhos e fundos de marca"),
        "azulejo": cor(C["azulejo"], "Botões, links e destaques"),
        "planalto": cor(C["planalto"], "Apoio sobre fundos escuros"),
        "voto": {
            "sim": cor(C["petroleo"], "Voto Sim"),
            "nao": cor(C["terracota"], "Voto Não"),
            "abstencao": cor(C["ocre"], "Abstenção"),
            "obstrucao": cor(C["lilas"], "Obstrução"),
        },
    },
    "fonte": {
        "titulo": {"$type": "fontFamily", "$value": [DISPLAY, "sans-serif"]},
        "texto": {"$type": "fontFamily", "$value": [TEXTO, "sans-serif"]},
    },
    "raio": {
        "pilula": {"$type": "dimension", "$value": "999px"},
        "cartao": {"$type": "dimension", "$value": "20px"},
        "campo": {"$type": "dimension", "$value": "12px"},
    },
}
(SAIDA / "tokens.json").write_text(json.dumps(tokens, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok", len(paginas), "páginas")
