# Manual de marca do Plenário

Identidade **Brasília acolhedora**: as cúpulas do Congresso dentro de um balão de conversa, o azul dos azulejos, fundo cor de areia e as fontes Bricolage Grotesque e Figtree.

## Conteúdo

| Pasta/arquivo | O que é |
| --- | --- |
| `paginas/` | As 9 páginas do manual (1440 × 1024): capa, essência, logo, regras do logo, cores, tipografia, elementos gráficos, tom de voz e aplicações |
| `logo/` | Símbolo e assinatura, nas versões azul (fundos claros) e areia (fundos escuros) |
| `tokens.json` | Cores, fontes e raios no formato W3C Design Tokens (DTCG) |
| `gerar.py` | Gera tudo acima. Para mudar uma cor ou um texto, edite e rode `python3 docs/marca/gerar.py docs/marca` |

## Como levar para o Figma

1. No Figma, instale as fontes **Bricolage Grotesque**, **Figtree** e **IBM Plex Mono** se ainda não aparecerem (todas são do Google Fonts e o Figma costuma já ter).
2. Crie um arquivo novo e arraste os 9 SVGs de `paginas/` para o canvas. Cada um vira um frame com textos e vetores editáveis.
3. Arraste os SVGs de `logo/` para uma página "Logo" e transforme cada um em componente (Ctrl/Cmd + Alt + K).
4. Para criar as cores e fontes como variáveis, importe `tokens.json` com um plugin que leia o formato W3C Design Tokens, como o Tokens Studio.

As quebras de linha dos parágrafos vêm fixas do SVG. Ao editar um texto longo no Figma, junte as linhas em uma caixa de texto só.
