#!/usr/bin/env python3
"""CP-01 (docs/game-design/visual/06-tasks/cards-portraits.csv): WebP -> PNG for the real MVP card scans, hero and
sidekick avatars and card backs, so UE (which does not decode WebP, HUD-AND-ICONS.md HI-05) can import them (CP-02).

Not one pixel changes (ВР-48: original art as is, no AI upscale, no resize / crop / sharpen / gamma or colour change):
every source is decoded (Image.open -> convert('RGBA')) and written as an 8-bit RGBA PNG with an sRGB chunk; PNG sources
are rewritten as RGBA too (one format for the import). The written file is decoded again and compared with the decoded
source: max |delta| over RGBA must be 0 and the size must be the source size.

Sources (local scrape only, never downloaded again; scraped-data/ is gitignored, ENV-U3 / GAP-019):
  cards    only the 27 records of art/imagegen/mvp-v1/reused-cardart.json, en.path and ru.path of each; the sha256 of
           the file is checked against the record BEFORE conversion - a mismatch is an error and nothing is written for
           that file (ВР-51: RU build = RU scans 287x398, EN build = EN scans 250x349).
  heroes   the hero JSON of the scrape (SvelteKit devalue payload: nodes[2].data, root fetchedHero), ВР-47 / ВР-50:
             fetchedHero.avatar            -> images/heroes/avatars/<basename of the URL>
             fetchedHero.sidekicks[].avatar -> images/heroes/sidekicks/<basename> (one file per distinct URL: the three
                                              Harpies share one picture, 02 §6.5)
             fetchedHero.cardBackImage     -> images/heroes/card-covers/<basename>
           ВР-CP17 (by delegation): the card back is the scrape's cardBackImage (card-covers), not whatever Hero.imageUrl
           points to now - backend/prisma/update-hero-images.ts:98 writes characterCardImage (character-cards/...) there.
           The run compares Hero.imageUrl / Hero.avatarUrl of King Arthur and Medusa in the reference DB (:5433, read
           through the backend GraphQL the admin :5480 uses, read-only query `heroes`) with the scrape and writes the
           result to the report; the backend is never changed (ВР-47).
           The MVP hero media are pinned below (EXPECTED_HERO_MEDIA, the hashes of the card): a different file is an error.

Outputs (OUT of git, default <repo>/scraped-data/derived/ue-media-v1, gitignored with scraped-data/):
  cards/<heroSlug>/<cardSlug>.<ru|en>.png   (heroSlug:cardSlug = stableContentKey, INT-014)
  avatars/<heroSlug>.png
  sidekicks/<heroSlug>-<sidekickSlug>.png   (king-arthur-merlin, medusa-harpies)
  backs/<heroSlug>.png
Report (in git, no pixels): art/cards-v1/media-convert-report.json - per file: key, input path + sha256, output path +
sha256, size, mode, pixelEqual. A re-run with unchanged inputs writes nothing (action "unchanged"; the output is still
decoded and compared) and leaves the report byte-identical.

  python tools/art/cards/convert_card_media.py [--scraped <dir>] [--out <dir>] [--report <json>] [--no-db]
                                               [--hero-api <graphql url>] [--force]
  python tools/art/cards/convert_card_media.py --check      (registry + source hashes only, nothing written)
Scrape directory order: --scraped, env UM_SCRAPED_DATA, <repo>/scraped-data (if it has images/), the main checkout
C:/Users/ren/WebstormProjects/unmached/unmached/scraped-data (a worktree has no scrape of its own).
Status of the result: «технически импортировано» (original art as is; frame and display are accepted in CP-13 / CP-15).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path, PurePosixPath

import numpy as np
from PIL import Image, PngImagePlugin

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
REGISTRY = REPO / "art/imagegen/mvp-v1/reused-cardart.json"
REPORT = REPO / "art/cards-v1/media-convert-report.json"
OUT_SUBDIR = Path("derived/ue-media-v1")
SCHEMA = "unmatched.card-media-convert/1"
HERO_API = "http://127.0.0.1:3000/graphql"
# MVP heroes (02 §6.4 / §6.5): heroSlug -> name in the scrape / the DB.
HEROES = {"king-arthur": "King Arthur", "medusa": "Medusa"}
# VC C4 (ВР-VC-20, CLOSEOUT п. 8): heroes the client shows only as a portrait - the server bot of VS_AI (T. Rex, the
# strongest hero the bot picks). Avatar only: no cards, no back, and a sidekick record without a name or an avatar
# (the bot's "Unknown" of the backend data) is skipped, its circle stays the monogram.
PORTRAIT_ONLY_HEROES = {"t-rex": "T. Rex"}
# The card's pinned MVP hero media (scraped-data/images/heroes/<sub>/<file>): sha256, size, mode.
EXPECTED_HERO_MEDIA = {
    "avatars/dgwIAej9v-Omrn0sSVs5i.webp": ("a93e817db892e2fed4375e8757a47a39e9e253d3076547fed752757a978f743a", (800, 800)),
    "avatars/bI206lUtJUQru-FOD8A74.webp": ("310b5bbcc0594f1441494e38d434e03849dc3518c349349f7d16ee3faccfe920", (402, 402)),
    "sidekicks/4Rl9Oq9N82zhatbTShnXn.webp": ("9e08817bd7955c00ce079aaf7893d687114bcfec34103b91618b629634026cd9", (128, 128)),
    "sidekicks/G42WIKYZ1cmwACVwMggzM.webp": ("1cfcad663bcd9e99df233bcd8b5c61c8fe97b354070a75542713929534ee5e62", (128, 128)),
    "card-covers/WWzu16BEFGsEdu5NsMbMI.png": ("c061ee8848390e9be86a49d963904bc8bff6bafb3dbfc70c40420af08801fda7", (768, 1051)),
    "card-covers/ROSMO3sRi6Jh1o7S_riGI.png": ("9b380cf4be7e2e4e0e319bc47b9f2aa4c0c72dc3aac587c0112f909440ca1b44", (768, 1051)),
    # VC C4: T. Rex avatar (Hero.avatarUrl of the backend = the scrape's fetchedHero.avatar)
    "avatars/9z9iaYFxdQpstwDftty0r.webp": ("7cec7e403457010944a3ddb9f6e016fface3aa8092da48aaaaeb9dd83ebf9900", (768, 768)),
}
SCAN_SIZE = {"ru": (287, 398), "en": (250, 349)}  # 02 §6.1 / ВР-51
KEY_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*:[a-z0-9]+(?:-[a-z0-9]+)*$")


class ConvertError(RuntimeError):
    """A source that must not be converted (missing, wrong sha256, wrong registry); the message names the key."""


# ------------------------------------------------------------------ helpers
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text_lf(path: Path) -> str:
    """sha256 of a text file as git stores it (CRLF -> LF: a core.autocrlf checkout hashes like the blob)."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def scraped_root(arg: str | None) -> Path:
    for cand in (arg, os.environ.get("UM_SCRAPED_DATA")):
        if cand:
            return Path(cand)
    local = REPO / "scraped-data"
    return local if (local / "images").is_dir() else MAIN_CHECKOUT / "scraped-data"


def scrape_path(root: Path, rel: str) -> Path:
    """'scraped-data/images/...' (registry form) or 'images/...' -> a file under the scrape root."""
    p = PurePosixPath(rel)
    if p.parts and p.parts[0] == "scraped-data":
        p = PurePosixPath(*p.parts[1:])
    return root / Path(*p.parts)


def rel_repo(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def scrape_rel(path: Path, root: Path) -> str:
    try:
        return "scraped-data/" + path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def decode_devalue(doc: dict, what: str) -> dict:
    """SvelteKit devalue payload: nodes[2].data is a flat array whose objects / arrays hold indices into the same
    array (negative = null); index 0 is the root (same decoder as tools/art/art_board_fixtures.py)."""
    nodes = doc.get("nodes") or []
    if len(nodes) < 3 or not isinstance(nodes[2], dict) or "data" not in nodes[2]:
        raise ConvertError(f"{what}: nodes[2].data missing (not a devalue payload)")
    data = nodes[2]["data"]

    def hydrate(index, depth=0):
        if depth > 64:
            raise ConvertError(f"{what}: devalue nesting too deep")
        if not isinstance(index, int) or index < 0:
            return None
        value = data[index]
        if isinstance(value, dict):
            return {k: hydrate(v, depth + 1) for k, v in value.items()}
        if isinstance(value, list):
            return [hydrate(v, depth + 1) for v in value]
        return value

    root = hydrate(0)
    if not isinstance(root, dict) or not isinstance(root.get("fetchedHero"), dict):
        raise ConvertError(f"{what}: root.fetchedHero missing")
    return root


def url_basename(url: str, what: str) -> str:
    if not isinstance(url, str) or "/" not in url:
        raise ConvertError(f"{what}: no URL")
    return url.rstrip("/").rsplit("/", 1)[1]


# ------------------------------------------------------------------ plan
def card_items(root: Path, registry_path: Path = REGISTRY) -> list[dict]:
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    cards = reg.get("cards")
    if not isinstance(cards, list) or not cards:
        raise ConvertError(f"{rel_repo(registry_path)}: no cards")
    items = []
    for card in cards:
        key = card.get("stableContentKey", "")
        if not KEY_RE.match(key):
            raise ConvertError(f"{key or card.get('assetKey')}: stableContentKey is not heroSlug:cardSlug")
        hero, name = key.split(":")
        for lang in ("ru", "en"):
            rec = card.get(lang) or {}
            if not rec.get("path") or not rec.get("sha256"):
                raise ConvertError(f"{key}.{lang}: no path / sha256 in the registry")
            items.append({"key": f"{key}.{lang}", "kind": "card", "hero": hero, "card": name, "lang": lang,
                          "src": scrape_path(root, rec["path"]), "srcRel": rec["path"], "sha256": rec["sha256"],
                          "size": SCAN_SIZE[lang], "out": Path("cards") / hero / f"{name}.{lang}.png"})
    return items


def hero_items(root: Path) -> tuple[list[dict], dict]:
    items, scrape = [], {}
    for hero, name in HEROES.items():
        jpath = root / "api" / "heroes" / f"{hero}.json"
        if not jpath.is_file():
            raise ConvertError(f"{hero}: hero JSON missing ({scrape_rel(jpath, root)})")
        fh = decode_devalue(json.loads(jpath.read_text(encoding="utf-8")), f"{hero}.json")["fetchedHero"]
        if fh.get("name") != name:
            raise ConvertError(f"{hero}: fetchedHero.name is {fh.get('name')!r}, expected {name!r}")
        avatar = url_basename(fh.get("avatar"), f"{hero}.avatar")
        back = url_basename(fh.get("cardBackImage"), f"{hero}.cardBackImage")
        scrape[hero] = {"name": name, "avatar": fh.get("avatar"), "cardBackImage": fh.get("cardBackImage"),
                        "characterCardImage": fh.get("characterCardImage")}
        plan = [("avatar", f"avatars/{avatar}", Path("avatars") / f"{hero}.png", f"portrait:{hero}")]
        seen = set()
        for sk in fh.get("sidekicks") or []:
            base = url_basename(sk.get("avatar"), f"{hero}.sidekicks[].avatar")
            if base in seen:
                continue  # the Harpies: one picture for the three (02 §6.5)
            seen.add(base)
            sk_slug = slug(sk.get("name") or "")
            if not sk_slug:
                raise ConvertError(f"{hero}: sidekick without a name")
            plan.append(("sidekick", f"sidekicks/{base}", Path("sidekicks") / f"{hero}-{sk_slug}.png",
                         f"portrait:{hero}:{sk_slug}"))
        plan.append(("back", f"card-covers/{back}", Path("backs") / f"{hero}.png", f"back:{hero}"))
        for kind, rel, out, key in plan:
            exp = EXPECTED_HERO_MEDIA.get(rel)
            if exp is None:
                raise ConvertError(f"{key}: {rel} is not the pinned MVP file (EXPECTED_HERO_MEDIA) - scrape changed?")
            items.append({"key": key, "kind": kind, "hero": hero, "src": root / "images" / "heroes" / rel,
                          "srcRel": f"scraped-data/images/heroes/{rel}", "sha256": exp[0], "size": exp[1], "out": out})
    for hero, name in PORTRAIT_ONLY_HEROES.items():
        jpath = root / "api" / "heroes" / f"{hero}.json"
        if not jpath.is_file():
            raise ConvertError(f"{hero}: hero JSON missing ({scrape_rel(jpath, root)})")
        fh = decode_devalue(json.loads(jpath.read_text(encoding="utf-8")), f"{hero}.json")["fetchedHero"]
        if fh.get("name") != name:
            raise ConvertError(f"{hero}: fetchedHero.name is {fh.get('name')!r}, expected {name!r}")
        rel = f"avatars/{url_basename(fh.get('avatar'), f'{hero}.avatar')}"
        scrape[hero] = {"name": name, "avatar": fh.get("avatar"), "cardBackImage": fh.get("cardBackImage"),
                        "characterCardImage": fh.get("characterCardImage")}
        exp = EXPECTED_HERO_MEDIA.get(rel)
        if exp is None:
            raise ConvertError(f"portrait:{hero}: {rel} is not the pinned file (EXPECTED_HERO_MEDIA) - scrape changed?")
        items.append({"key": f"portrait:{hero}", "kind": "avatar", "hero": hero, "src": root / "images" / "heroes" / rel,
                      "srcRel": f"scraped-data/images/heroes/{rel}", "sha256": exp[0], "size": exp[1],
                      "out": Path("avatars") / f"{hero}.png"})
    return items, scrape


# ------------------------------------------------------------------ conversion
def decode_rgba(path: Path) -> tuple[np.ndarray, str]:
    with Image.open(path) as im:
        mode = im.mode
        rgba = np.asarray(im.convert("RGBA"))
    return rgba, mode


def png_bytes(rgba: np.ndarray) -> bytes:
    """8-bit RGBA PNG with an sRGB chunk (rendering intent 0), no other metadata (no ICC, no gAMA, no dpi)."""
    import io

    im = Image.frombytes("RGBA", (rgba.shape[1], rgba.shape[0]), np.ascontiguousarray(rgba).tobytes())
    info = PngImagePlugin.PngInfo()
    info.add(b"sRGB", b"\x00")
    buf = io.BytesIO()
    im.save(buf, format="PNG", pnginfo=info, compress_level=6)
    return buf.getvalue()


def convert_item(item: dict, out_root: Path, previous: dict | None, force: bool) -> tuple[dict, str]:
    src: Path = item["src"]
    key = item["key"]
    if not src.is_file():
        raise ConvertError(f"{key}: source not found ({item['srcRel']})")
    got = sha256_file(src)
    if got != item["sha256"]:
        raise ConvertError(f"{key}: sha256 of {item['srcRel']} is {got[:12]}..., the registry has "
                           f"{item['sha256'][:12]}... - not converted")
    rgba, mode = decode_rgba(src)
    size = (rgba.shape[1], rgba.shape[0])
    if tuple(item["size"]) != size:
        raise ConvertError(f"{key}: source is {size[0]}x{size[1]}, expected {item['size'][0]}x{item['size'][1]}")
    out = out_root / item["out"]
    action = "written"
    if (not force and previous and previous.get("in", {}).get("sha256") == got and out.is_file()
            and sha256_file(out) == previous.get("out", {}).get("sha256")):
        action = "unchanged"
    else:
        data = png_bytes(rgba)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.is_file() and out.read_bytes() == data:
            action = "unchanged"
        else:
            out.write_bytes(data)
    back, back_mode = decode_rgba(out)
    equal = back.shape == rgba.shape and bool(np.array_equal(back, rgba))
    max_delta = int(np.abs(back.astype(np.int16) - rgba.astype(np.int16)).max()) if back.shape == rgba.shape else 255
    with Image.open(out) as im:
        out_mode, out_size = im.mode, im.size
    entry = {"key": key, "kind": item["kind"],
             "in": {"path": item["srcRel"], "sha256": got, "mode": mode, "format": src.suffix.lstrip(".").lower()},
             "out": {"path": item["out"].as_posix(), "sha256": sha256_file(out), "mode": out_mode},
             "size": list(size), "outSize": list(out_size), "pixelEqual": equal and tuple(out_size) == size,
             "maxAbsDelta": max_delta}
    return entry, action


# ------------------------------------------------------------------ Hero.imageUrl (ВР-CP17)
def db_check(api: str, scrape: dict, timeout: float = 5.0) -> dict:
    """Read-only GraphQL query `heroes` of the backend the admin uses (reference DB :5433); compares Hero.imageUrl with
    the scrape's cardBackImage and Hero.avatarUrl with avatar (by URL basename). Never writes."""
    body = json.dumps({"query": "{ heroes { name imageUrl avatarUrl } }"}).encode("utf-8")
    req = urllib.request.Request(api, data=body, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (localhost, fixed query)
            payload = json.loads(resp.read().decode("utf-8"))
        heroes = {h["name"]: h for h in payload["data"]["heroes"]}
    except (urllib.error.URLError, OSError, KeyError, TypeError, ValueError) as exc:
        return {"status": "unreachable", "api": api, "error": str(exc)[:200]}
    per, mismatch = {}, False
    for slug_, s in scrape.items():
        h = heroes.get(s["name"])
        if h is None:
            per[slug_] = {"status": "missing-in-db"}
            mismatch = True
            continue
        img_ok = (h.get("imageUrl") or "").rsplit("/", 1)[-1] == s["cardBackImage"].rsplit("/", 1)[-1]
        ava_ok = (h.get("avatarUrl") or "").rsplit("/", 1)[-1] == s["avatar"].rsplit("/", 1)[-1]
        points = ("cardBackImage (card-covers)" if img_ok
                  else "characterCardImage (character-cards)" if (h.get("imageUrl") or "").rsplit("/", 1)[-1]
                  == (s.get("characterCardImage") or "").rsplit("/", 1)[-1] else "other")
        per[slug_] = {"dbImageUrl": h.get("imageUrl"), "dbAvatarUrl": h.get("avatarUrl"),
                      "scrapeCardBackImage": s["cardBackImage"], "scrapeAvatar": s["avatar"],
                      "imageUrlPointsTo": points, "imageUrlMatchesCardBack": img_ok, "avatarUrlMatches": ava_ok}
        mismatch = mismatch or not (img_ok and ava_ok)
    return {"status": "mismatch" if mismatch else "match", "api": api,
            "via": "backend GraphQL `heroes` (the API of the admin :5480; reference DB :5433), read-only",
            "heroes": per,
            "note": ("ВР-CP17: the card back is the scrape's cardBackImage either way; a mismatch is reported, the "
                     "backend is not changed (ВР-47)")}


# ------------------------------------------------------------------ run
def run(scraped: Path, out_root: Path, report_path: Path | None, *, check: bool = False, force: bool = False,
        db: bool = True, hero_api: str = HERO_API, registry_path: Path = REGISTRY) -> dict:
    started = time.time()
    previous_report = {}
    if report_path is not None and report_path.is_file():
        try:
            previous_report = json.loads(report_path.read_text(encoding="utf-8"))
        except ValueError:
            previous_report = {}
    previous = {e["key"]: e for e in previous_report.get("files", [])}
    items = card_items(scraped, registry_path)
    heroes, scrape = hero_items(scraped)
    items += heroes
    keys = [i["key"] for i in items]
    if len(set(keys)) != len(keys):
        raise ConvertError("duplicate output keys in the plan")
    if check:
        errors = []
        for item in items:
            if not item["src"].is_file():
                errors.append(f"{item['key']}: source not found ({item['srcRel']})")
            elif sha256_file(item["src"]) != item["sha256"]:
                errors.append(f"{item['key']}: sha256 differs from the registry")
        return {"mode": "check", "files": len(items), "errors": errors, "ok": not errors}
    entries, actions = [], {"written": 0, "unchanged": 0}
    for item in items:
        entry, action = convert_item(item, out_root, previous.get(item["key"]), force)
        entries.append(entry)
        actions[action] += 1
    check_db = db_check(hero_api, scrape) if db else {"status": "skipped"}
    old_db = previous_report.get("heroImageUrlCheck") or {}
    if check_db["status"] in ("skipped", "unreachable") and old_db.get("status") in ("match", "mismatch"):
        check_db = dict(old_db, kept="previous result kept: this run could not query the DB (" + check_db["status"] + ")")
    counts = {}
    for e in entries:
        counts[e["kind"]] = counts.get(e["kind"], 0) + 1
    report = {
        "schema": SCHEMA,
        "tool": "tools/art/cards/convert_card_media.py",
        "card": "CP-01",
        "status": "технически импортировано (оригинальный арт как есть, ВР-48; рамка и показ - CP-13 / CP-15)",
        "decisions": ["ВР-47", "ВР-48", "ВР-50", "ВР-51", "ВР-CP17"],
        "registry": {"path": rel_repo(registry_path), "sha256Lf": sha256_text_lf(registry_path),
                     "cards": len({e["key"].rsplit(".", 1)[0] for e in entries if e["kind"] == "card"})},
        "outRoot": "scraped-data/derived/ue-media-v1 (out of git, ENV-U3 / GAP-019)",
        "count": len(entries),
        "counts": dict(sorted(counts.items())),
        "allPixelEqual": all(e["pixelEqual"] for e in entries),
        "heroImageUrlCheck": check_db,
        "files": entries,
    }
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    if report_path is not None:
        old_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else None
        if old_text != text:
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(text, encoding="utf-8", newline="\n")
    report["_run"] = {"actions": actions, "seconds": round(time.time() - started, 2), "outDir": str(out_root),
                      "scraped": str(scraped)}
    return report


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--scraped", default=None, help="scrape root (with images/ and api/)")
    ap.add_argument("--out", default=None, help="output root (default <repo>/scraped-data/derived/ue-media-v1)")
    ap.add_argument("--report", default=str(REPORT), help="report JSON (in git)")
    ap.add_argument("--registry", default=str(REGISTRY), help="reused-cardart.json")
    ap.add_argument("--check", action="store_true", help="verify the sources only, write nothing")
    ap.add_argument("--force", action="store_true", help="rewrite every PNG")
    ap.add_argument("--no-db", action="store_true", help="skip the Hero.imageUrl check")
    ap.add_argument("--hero-api", default=HERO_API, help="backend GraphQL endpoint (read-only query `heroes`)")
    args = ap.parse_args(argv)
    scraped = scraped_root(args.scraped)
    out_root = Path(args.out) if args.out else REPO / "scraped-data" / OUT_SUBDIR
    try:
        res = run(scraped, out_root, Path(args.report) if args.report else None, check=args.check, force=args.force,
                  db=not args.no_db, hero_api=args.hero_api, registry_path=Path(args.registry))
    except ConvertError as exc:
        print(f"CARD-MEDIA-CONVERT error: {exc}")
        return 1
    if res.get("mode") == "check":
        for e in res["errors"]:
            print("  " + e)
        print(f"CARD-MEDIA-CONVERT check {'ok' if res['ok'] else 'FAILED'} files={res['files']} scraped={scraped}")
        return 0 if res["ok"] else 1
    run_info = res["_run"]
    print(f"CARD-MEDIA-CONVERT {'ok' if res['allPixelEqual'] else 'FAILED'} files={res['count']} "
          f"written={run_info['actions']['written']} unchanged={run_info['actions']['unchanged']} "
          f"pixelEqual={sum(e['pixelEqual'] for e in res['files'])}/{res['count']} "
          f"heroImageUrl={res['heroImageUrlCheck']['status']} seconds={run_info['seconds']} out={out_root}")
    return 0 if res["allPixelEqual"] else 1


if __name__ == "__main__":
    sys.exit(main())
