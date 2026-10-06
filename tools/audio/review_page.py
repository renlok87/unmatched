"""Local listening page for the user's acceptance by ear (G-ART, 05-production-plan §2.6).

    python tools/audio/review_page.py --final C:/tmp/audio-src/final --out C:/tmp/audio-review/index.html
           [--casting C:/tmp/audio-src/vo/recast/casting --casting-old C:/tmp/audio-src/final/vo-v1-cassius]

One page with a player per finished sound: music layers (L1, L2, full loop), stings, VO lines with their EN / RU
text, SFX by category, ambience. The audio stays outside git; the page links the files by absolute file:// URLs.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from vo_batch import lines as script_lines  # noqa: E402

CSS = """
:root{--bg:#f6f3ee;--fg:#22201c;--muted:#6b665d;--card:#fff;--line:#e2dccf;--acc:#7b4e1c}
@media (prefers-color-scheme:dark){:root{--bg:#1a1916;--fg:#ece7dc;--muted:#a39d90;--card:#24221e;--line:#38342d;--acc:#d9a35a}}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.45 system-ui,Segoe UI,sans-serif}
main{max-width:1100px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:24px;margin:0 0 4px}h2{margin:32px 0 8px;font-size:19px;border-bottom:1px solid var(--line);padding-bottom:4px}
p.note{color:var(--muted);margin:0 0 16px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:10px}
.item{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px}
.item b{font-size:13px;word-break:break-all}.item .t{color:var(--muted);font-size:13px;margin:2px 0 4px}
audio{width:100%;height:32px}
"""


def item(path: Path, title: str, text: str = "") -> str:
    url = "file:///" + str(path).replace("\\", "/")
    t = f'<div class="t">{html.escape(text)}</div>' if text else ""
    return (f'<div class="item"><b>{html.escape(title)}</b>{t}'
            f'<audio controls preload="none" src="{html.escape(url)}"></audio></div>')


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--final", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--casting", help="vo_batch casting output (<label>/<take>/<take>.mp3): one row per voice")
    ap.add_argument("--casting-old", help="finals of the previous voice, for the same probe lines")
    args = ap.parse_args(argv)
    final = Path(args.final)
    parts = ["<!doctype html><html lang='ru'><head><meta charset='utf-8'>"
             "<meta name='viewport' content='width=device-width,initial-scale=1'><title>Звук Unmatched</title>"
             f"<style>{CSS}</style></head><body><main><h1>Звук Unmatched — прослушивание</h1>"
             "<p class='note'>AU-S4, 2026-10-05. Выбор сделан агентом по метрикам (07-production-log.md); "
             "приёмка на слух — ваша. Файлы лежат вне git, в C:/tmp/audio-src/final.</p>"]
    if args.casting:
        parts.append("<h2>Кастинг голоса Артура (2026-10-06)</h2><p class='note'>Выбран Jayce — Grim (07 §8). "
                     "Те же пробные строки другими голосами — для сравнения на слух.</p>")
        for label in sorted(Path(args.casting).iterdir()):
            files = sorted(label.glob("*/*.mp3"))
            if files:
                parts.append(f"<h3>{html.escape(label.name.split('_', 1)[-1])}</h3><div class='grid'>"
                             + "".join(item(f, f.stem) for f in files) + "</div>")
        if args.casting_old:
            probes = sorted({f.parent.name.split("_t")[0][3:].replace("_", "-") for f in Path(args.casting).glob("*/*/*.mp3")})
            old = [Path(args.casting_old) / f"{p}.wav" for p in probes if (Path(args.casting_old) / f"{p}.wav").exists()]
            parts.append("<h3>cassius (прежний голос)</h3><div class='grid'>" + "".join(item(f, f.stem) for f in old) + "</div>")
    parts.append("<h2>Музыка: слои и петли</h2><div class='grid'>")
    for f in sorted((final / "music").glob("*-[Lf]*[0-9a-z].wav")):
        if f.stem.endswith("_16"):
            continue
        parts.append(item(f, f.stem, {"L1": "манёвр", "L2": "бой (ударные+бас)", "full": "вместе"}.get(
            f.stem.rsplit("-", 1)[-1], "")))
    parts.append("</div><h2>Стинги</h2><div class='grid'>")
    for f in sorted((final / "stings").glob("*.wav")):
        if not f.stem.endswith("_16"):
            meta = json.loads((final / "stings" / f"{f.stem}.json").read_text(encoding="utf-8"))
            parts.append(item(f, f.stem, f"{meta['seconds']} с, мотив {meta['motif_sim']}"))
    parts.append("</div><h2>Реплики</h2><div class='grid'>")
    for ln in script_lines():
        f = final / "vo" / f"{ln['id']}.wav"
        if f.exists():
            parts.append(item(f, ln["id"], f"{ln['en']} — {ln['ru']}" if ln["en"] else ln["tags"]))
    for f in sorted((final / "vo").glob("HARPY-*.wav")) + sorted((final / "vo").glob("FX-*.wav")):
        parts.append(item(f, f.stem))
    parts.append("</div>")
    groups = {"UI": "Интерфейс", "CRD": "Карты", "BRD": "Поле", "CMB": "Бой", "DTH": "Смерть", "FX": "Эффекты",
              "STG": "Стинг лимита руки"}
    for prefix, title in groups.items():
        files = sorted((final / "sfx").glob(f"{prefix}-*.wav"))
        if files:
            parts.append(f"<h2>{title}</h2><div class='grid'>" + "".join(item(f, f.stem) for f in files) + "</div>")
    parts.append("<h2>Окружение</h2><div class='grid'>")
    for f in sorted((final / "amb").glob("*.wav")):
        parts.append(item(f, f.stem))
    parts.append("</div></main></body></html>")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(parts), encoding="utf-8")
    print(f"{out} ({sum(p.count('<audio') for p in parts)} players)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
