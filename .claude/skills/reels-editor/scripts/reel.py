"""Edita um vídeo bruto em um Reel/TikTok 9:16 no estilo do Plenário.

Pipeline: transcreve (faster-whisper, tempo por palavra) -> corta silêncios
(jump cuts) -> reenquadra para 1080x1920 -> zoom alternado entre cortes ->
legendas palavra a palavra (.ass) -> normaliza áudio a -14 LUFS -> exporta H.264.

Uso:
  python reel.py bruto.mp4 -o final.mp4 [--style dalen|demo] [--gap 0.35]
                 [--lang pt] [--no-zoom] [--no-captions] [--model small]
Gera também final.words.json (transcrição) e final.ass (legendas) ao lado do vídeo.
"""
import argparse, glob, json, os, shutil, subprocess, sys
from pathlib import Path

W, H = 1080, 1920

# Estilos de legenda (ASS). Cores em &HBBGGRR.
STYLES = {
    # Talking head estilo Daniel Dalen: pequeno, terço superior, acima da cabeça.
    "dalen": dict(font="Segoe UI", size=62, bold=-1, align=8, margin_v=330,
                  active="&H00FFFFFF", upcoming="&H00A0A0A0", outline=0, shadow=2),
    # Demo de produto estilo farza: centralizado, um pouco abaixo do meio.
    "demo": dict(font="Segoe UI Semibold", size=72, bold=0, align=5, margin_v=0,
                 active="&H00FFFFFF", upcoming="&H00FFFFFF", outline=0, shadow=3),
}


def find_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    hits = glob.glob(os.path.expandvars(
        r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg*\ffmpeg-*\bin\ffmpeg.exe"))
    if hits:
        return hits[0]
    sys.exit("ffmpeg não encontrado. Instale com: winget install Gyan.FFmpeg")


def load_audio(ffmpeg, path):
    import numpy as np
    raw = subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-i", path,
                          "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.int16).astype(np.float32) / 32768.0


def transcribe(ffmpeg, path, lang, model_name):
    os.environ.setdefault("HF_HOME", os.path.expandvars(r"%LOCALAPPDATA%\hf-models"))
    from faster_whisper import WhisperModel
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segs, _ = model.transcribe(load_audio(ffmpeg, path), language=lang,
                               word_timestamps=True, vad_filter=True)
    return [{"w": w.word.strip(), "s": round(w.start, 3), "e": round(w.end, 3)}
            for s in segs for w in s.words if w.word.strip()]


def speech_spans(words, gap, pad, duration):
    """Agrupa palavras em trechos de fala; pausas maiores que `gap` viram corte."""
    spans = []
    for w in words:
        if spans and w["s"] - spans[-1][1] <= gap:
            spans[-1][1] = w["e"]
        else:
            spans.append([w["s"], w["e"]])
    return [(max(0, s - pad), min(duration, e + pad)) for s, e in spans]


def chunk_words(words, style):
    """Agrupa palavras (já no tempo final) em blocos de legenda exibidos juntos.

    Cada item de `words` é {"w": texto, "s": início, "e": fim}. Retorna uma
    lista de blocos, cada bloco uma lista de palavras.
    """
    # TODO(human): defina como as palavras são agrupadas em blocos de legenda.
    raise NotImplementedError("chunk_words ainda não implementada")


def ass_time(t):
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def write_ass(words, style_name, path):
    st = STYLES[style_name]
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}",
        "WrapStyle: 0", "", "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Alignment, MarginL, MarginR, MarginV, Outline, Shadow, BorderStyle",
        f"Style: Cap,{st['font']},{st['size']},{st['active']},&H00000000,&H80000000,"
        f"{st['bold']},{st['align']},90,90,{st['margin_v']},{st['outline']},{st['shadow']},1",
        "", "[Events]", "Format: Layer, Start, End, Style, Text",
    ]
    for chunk in chunk_words(words, style_name):
        for i, w in enumerate(chunk):
            end = chunk[i + 1]["s"] if i + 1 < len(chunk) else w["e"] + 0.15
            spoken = " ".join(x["w"] for x in chunk[: i + 1])
            rest = " ".join(x["w"] for x in chunk[i + 1:])
            text = spoken + (f" {{\\c{st['upcoming']}}}{rest}" if rest else "")
            lines.append(f"Dialogue: 0,{ass_time(w['s'])},{ass_time(end)},Cap,{text}")
    Path(path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input")
    ap.add_argument("-o", "--output", required=True)
    ap.add_argument("--style", choices=STYLES, default="dalen")
    ap.add_argument("--gap", type=float, default=0.35, help="pausa (s) que vira corte")
    ap.add_argument("--pad", type=float, default=0.08, help="respiro (s) em cada corte")
    ap.add_argument("--lang", default="pt")
    ap.add_argument("--model", default="small")
    ap.add_argument("--zoom", type=float, default=1.12, help="zoom dos cortes ímpares")
    ap.add_argument("--no-zoom", action="store_true")
    ap.add_argument("--no-captions", action="store_true")
    a = ap.parse_args()

    ffmpeg = find_ffmpeg()
    src, out = Path(a.input).resolve(), Path(a.output).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = float(subprocess.run(
        [str(Path(ffmpeg).with_name("ffprobe")), "-v", "error", "-show_entries",
         "format=duration", "-of", "csv=p=0", str(src)],
        capture_output=True, text=True, check=True).stdout)

    print("1/4 transcrevendo…")
    words = transcribe(ffmpeg, str(src), a.lang, a.model)
    if not words:
        sys.exit("Nenhuma fala detectada.")
    spans = speech_spans(words, a.gap, a.pad, duration)

    # Remapeia o tempo das palavras para a linha do tempo já cortada.
    new_words, offset, i = [], 0.0, 0
    for s, e in spans:
        while i < len(words) and words[i]["s"] < e:
            w = words[i]
            new_words.append({"w": w["w"], "s": round(offset + max(w["s"] - s, 0), 3),
                              "e": round(offset + min(w["e"], e) - s, 3)})
            i += 1
        offset += e - s
    out.with_suffix(".words.json").write_text(
        json.dumps({"source": str(src), "spans": spans, "words": new_words},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    cut = duration - offset
    print(f"2/4 {len(spans)} trechos de fala; {cut:.1f}s de silêncio removidos "
          f"({duration:.1f}s -> {offset:.1f}s)")

    # Monta o filtro: cada trecho é recortado, reenquadrado e (alternadamente) ampliado.
    fc, cat = [], []
    cover = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    for k, (s, e) in enumerate(spans):
        z = a.zoom if (k % 2 and not a.no_zoom) else 1.0
        zoom = (f",scale=iw*{z}:ih*{z},crop={W}:{H}:(iw-{W})/2:(ih-{H})*0.35"
                if z != 1.0 else "")
        fc.append(f"[0:v]trim={s:.3f}:{e:.3f},setpts=PTS-STARTPTS,{cover}{zoom},"
                  f"setsar=1[v{k}]")
        fc.append(f"[0:a]atrim={s:.3f}:{e:.3f},asetpts=PTS-STARTPTS[a{k}]")
        cat.append(f"[v{k}][a{k}]")
    fc.append(f"{''.join(cat)}concat=n={len(spans)}:v=1:a=1[vc][ac]")
    if a.no_captions:
        fc.append("[vc]null[vo]")
    else:
        write_ass(new_words, a.style, out.with_suffix(".ass"))
        fc.append(f"[vc]subtitles={out.with_suffix('.ass').name}[vo]")
    fc.append("[ac]loudnorm=I=-14:TP=-1:LRA=11,aresample=48000[ao]")
    script = out.with_suffix(".filter.txt")
    script.write_text(";\n".join(fc), encoding="utf-8")

    print("3/4 renderizando…")
    # cwd = pasta de saída: o filtro `subtitles` recebe nome relativo (evita escapar C:\).
    r = subprocess.run([ffmpeg, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                        "-i", str(src), "-/filter_complex", script.name,
                        "-map", "[vo]", "-map", "[ao]", "-r", "30",
                        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                        "-movflags", "+faststart", str(out)], cwd=out.parent)
    if r.returncode:
        sys.exit(f"ffmpeg falhou (código {r.returncode}). Filtro em {script}")
    script.unlink()
    print(f"4/4 pronto: {out}")


if __name__ == "__main__":
    main()
