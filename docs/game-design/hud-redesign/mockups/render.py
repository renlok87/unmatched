"""Render HUD concept mockups (HTML over a real board frame) to JPG at 1920x1080.

Usage: python docs/game-design/hud-redesign/mockups/render.py [name ...]
Sources: mockups/src/<name>.html. Output: mockups/<name>.jpg.
The HTML files load real game media from scraped-data/derived/ue-media-v1 (git-ignored, local only)
and the clean Marmoreal bench frame from docs/art-pipeline/evidence.
"""
import sys
from pathlib import Path

import json

from playwright.sync_api import sync_playwright
from PIL import Image

HERE = Path(__file__).resolve().parent
SRC = HERE / "src"


def main(names):
    if not names:
        names = sorted(p.stem for p in SRC.glob("*.html") if not p.stem.startswith("_"))
    meta = json.loads((SRC / "_meta.json").read_text(encoding="utf-8")) if (SRC / "_meta.json").exists() else {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name in names:
            m = meta.get(name, {"w": 1920, "h": 1080, "scale": 1})
            page = browser.new_page(viewport={"width": m["w"], "height": m["h"]}, device_scale_factor=m["scale"])
            src = SRC / f"{name}.html"
            page.goto(src.as_uri())
            page.wait_for_load_state("networkidle")
            page.evaluate("document.fonts.ready")
            png = HERE / f"{name}.png"
            page.screenshot(path=str(png), full_page=False)
            Image.open(png).convert("RGB").save(HERE / f"{name}.jpg", quality=88)
            png.unlink()
            page.close()
            print("rendered", name)
        browser.close()


if __name__ == "__main__":
    main(sys.argv[1:])
