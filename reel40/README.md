# 40-second reels (scene template)

- `template.html` – canvas template; `setup(config)` + `render(t)`. Visual types: timer, bigText, apart, merge, flow, list, twoBars, drain, arc, line, messenger, chore, lock, questions, check, outward, dim, quote, spark, hadith, cta.
- `example-configs.json` – the 5 configs for sheet rows 1–5 (copy the shape for new rows).
- `render.py MODE OUTDIR CONFIGS.json [rows]` – MODE `preview` writes one frame per scene, `full` writes `reel-rowN-40s.mp4` with whoosh/tick/pop SFX.
- `bed.py SRC OUT.wav 40` – loops `assets/bg-audio.mp3` with 0.5 s crossfades to 40 s, fades in 1 s / out 2 s.
- Final mix: `ffmpeg -i reel.mp4 -i bed.wav -filter_complex "[1:a]volume=0.8[b];[0:a]volume=0.9[s];[b][s]amix=inputs=2:normalize=0:duration=first,alimiter=limit=0.95[a]" -map 0:v -map "[a]" -c:v copy -c:a aac -b:a 192k -movflags +faststart out.mp4`
