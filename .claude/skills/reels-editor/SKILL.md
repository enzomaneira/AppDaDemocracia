---
name: reels-editor
description: Edita vídeos brutos em Reels/TikTok/Shorts 9:16 no estilo do Plenário (inspirado em Daniel Dalen para talking head e em farza para demo de produto) — corta silêncios, reenquadra, aplica zoom entre cortes, queima legendas palavra a palavra e normaliza áudio. Use quando o usuário pedir para editar, cortar, legendar ou exportar um vídeo curto.
---

# Editor de Reels do Plenário

## Ferramentas instaladas

- **ffmpeg 9** (winget `Gyan.FFmpeg`). Se `ffmpeg` não estiver no PATH do shell atual, o script acha o executável sozinho em `%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\…\bin`.
- **faster-whisper** (modelo `small`, CPU int8) — cache em `%LOCALAPPDATA%\hf-models` (o `~/.cache` é bloqueado pelo sandbox).
- **yt-dlp** — só para baixar *referências* de estilo, nunca para reutilizar conteúdo de terceiros.

## Comando principal

```bash
python ~/.claude/skills/reels-editor/scripts/reel.py BRUTO.mp4 -o SAIDA.mp4 --style dalen
```

| Opção | Padrão | Quando mudar |
|---|---|---|
| `--style dalen\|demo` | `dalen` | `demo` para gravação de tela / demonstração do app |
| `--gap` | `0.35` | ↓ 0.25 para ritmo mais agressivo; ↑ 0.5 se cortar respirações naturais |
| `--zoom` | `1.12` | 1.0–1.2; acima disso o rosto pixeliza em fonte 1080p |
| `--lang` | `pt` | idioma da fala |
| `--no-zoom`, `--no-captions` | — | quando o vídeo já tem legenda/edição própria |

Saídas ao lado do vídeo: `SAIDA.words.json` (transcrição com tempos, já na linha do tempo cortada) e `SAIDA.ass` (legendas editáveis — corrija erros de transcrição aqui e rode de novo só a renderização, se preciso).

## Processo

1. **Inspecione** o bruto: `ffprobe` (resolução, fps, duração) e uma folha de quadros (`-vf "fps=1,scale=180:-1,tile=8x4"`) lida com a ferramenta Read.
2. **Edite** com `reel.py`.
3. **Verifique antes de entregar** — sempre:
   - `ffprobe`: 1080×1920, 30 fps.
   - `loudnorm=print_format=summary`: −14 LUFS ±1, pico ≤ −1 dBTP.
   - Folha de quadros do resultado: legenda legível, não cobre o rosto, nada cortado nas bordas.
   - Leia o `.words.json`: nomes de parlamentares, partidos e números precisam estar **exatos** (Whisper erra nomes próprios). Corrija no `.ass`.
4. **Entregue** caminho do arquivo + duração final + o que foi cortado + pontos que pedem decisão humana.

## Estilo

Detalhes medidos nas referências em [references/estilos.md](references/estilos.md). Resumo:

- **Gancho em 0,0 s.** Nada de "oi pessoal". Se o bruto começa com enrolação, corte até a primeira frase forte.
- **Sem silêncio.** Pausas > 0,35 s viram jump cut; o zoom alternado disfarça o corte.
- **Legenda pequena, 1–4 palavras, palavra falada em branco e as próximas em cinza**, no terço superior (dalen) ou no centro (demo).
- **CTA de comentário** ("Comente PLENÁRIO que eu te mando o acesso") — nas referências gerou 1 comentário a cada 4 curtidas.
- **Prova visual** (print, tela do app, manchete) entra como overlay curto no topo.

## Regras do Plenário

As restrições de marca valem para vídeo: leia "Princípios de marca" e "Restrições inegociáveis" em `~/.claude/agents/cmo.md`. Em especial: neutralidade política (não corte falas de forma que mude o sentido do que um parlamentar disse) e todo número na tela com fonte oficial.
