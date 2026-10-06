"""CP-02 (docs/game-design/visual/06-tasks/cards-portraits.csv): import the CP-01 PNGs (real card scans, card backs,
hero / sidekick avatars) into UE and write the key registry the client looks textures up by (INT-014: heroSlug:cardSlug,
never a cuid, never a URL at runtime - INT-015).

Sources: the CP-01 outputs scraped-data/derived/ue-media-v1 (out of git) listed in art/cards-v1/media-convert-report.json;
the sha256 of every PNG is checked against that report before import (a missing / different file is never imported).

Destinations (ВР-CP07 by delegation, refines INT-016; '-' -> '_' in names as T_IV3_*; /Game/S08 is cooked through
DirectoriesToAlwaysCook, /Game/Textures/Cards of manifest 06 is not):
  /Game/S08/UI/Cards/<hero>/T_Card_<hero>_<card>_<RU|EN>
  /Game/S08/UI/CardBacks/T_CardBack_<hero>
  /Game/S08/UI/Portraits/T_Portrait_<hero>  and  T_Portrait_<hero>_<sidekick>
The uassets stay OUT of git (unreal/Unmatched/.gitignore Content/; no git add -f: third-party art, GAP-019 / ENV-U3).
Another checkout gets them by running this script after convert_card_media.py.

Texture settings (ВР-CP03 by delegation, refines 02 §6.1 "no mip": trilinear needs mips and the discard chip 32x45 is
0.11x a scan): power_of_two_mode PAD_TO_POWER_OF_TWO (287x398 -> 512x512, 250x349 -> 256x512, 402^2 -> 512^2,
800^2 -> 1024^2, 768x1051 -> 1024x2048, 128^2 stays; the source pixels are never resampled - padding, not stretching;
the source sits in the top-left, uv = src / pad), padding_color #061623 alpha 0 (card.navy), mip_gen_settings
TMGS_SIMPLE_AVERAGE, filter TF_TRILINEAR, compression TC_BC7, lod_group TEXTUREGROUP_UI, srgb, never_stream,
address_x / address_y TA_CLAMP.

Registry: unreal/Unmatched/Config/Cards/S08CardMedia.json (in git, no pixels; read by UI/UmCardMedia.h, staged by
Unmatched.Build.cs): per entry key, kind, lang (cards), object path, src, pad, uv = src / pad, sha256 of the PNG; portraits
also disc [cx, cy, d] in fractions of the source side - the ВР-CP01 starting numbers until CP-07 is reviewed.
Report: art/cards-v1/ue-import-report.json - asset path, source sha256, the final settings read back from the asset,
platform size, mips, resource size.

Runs inside the editor (the editor must be CLOSED - the commandlet holds the project):
  UnrealEditor-Cmd.exe <repo>/unreal/Unmatched/Unmatched.uproject -run=pythonscript
      -script="<repo>/tools/art/cards/ue_import_card_media.py --all" -unattended -nosplash -nullrhi
  (arguments inside the -script quotes; env UM_CARD_MEDIA_ARGS="--cards medusa" works too)
Modes: --portraits | --backs | --cards <heroSlug> | --frames | --all (default). --frames imports nothing yet: the card
frame textures come with CP-13. Idempotent: a texture whose metadata tag CardMediaSourceSha256 equals the PNG sha256 and
whose settings already match is not touched ("unchanged"); --force re-imports.
Plain Python (no UE):
  python tools/art/cards/ue_import_card_media.py --write-registry   (registry from the CP-01 report)
  python tools/art/cards/ue_import_card_media.py --check            (registry up to date + every PNG present with its sha)
Derived directory order: --derived, env UM_CARD_MEDIA_DERIVED, <repo>/scraped-data/derived/ue-media-v1 (if present), the
main checkout's scraped-data/derived/ue-media-v1.
Status: «технически импортировано» (original art as is; frame and display are accepted in CP-13 / CP-15).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
import sys
import time
from pathlib import Path

try:  # inside UnrealEditor(-Cmd) only
    import unreal as u  # type: ignore
except ImportError:  # pragma: no cover - plain Python
    u = None

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAIN_CHECKOUT = Path("C:/Users/ren/WebstormProjects/unmached/unmached")
CONVERT_REPORT = REPO / "art/cards-v1/media-convert-report.json"
REGISTRY = REPO / "unreal/Unmatched/Config/Cards/S08CardMedia.json"
REPORT = REPO / "art/cards-v1/ue-import-report.json"
REGISTRY_SCHEMA = "unmatched.s08-card-media/1"
REPORT_SCHEMA = "unmatched.card-media-ue-import/1"
ROOT_CARDS = "/Game/S08/UI/Cards"
ROOT_BACKS = "/Game/S08/UI/CardBacks"
ROOT_PORTRAITS = "/Game/S08/UI/Portraits"
SHA_TAG = "CardMediaSourceSha256"
PAD_COLOR = (0x06, 0x16, 0x23, 0)  # card.navy #061623, alpha 0
# ВР-CP01 (by delegation, CP-07 row): starting portrait circles (centre x, centre y, diameter) in fractions of the source
# side; CP-07 replaces them after its review (portrait-crops.json).
DISC_START = {
    "portrait:king-arthur": [0.49, 0.43, 0.60],
    "portrait:medusa": [0.44, 0.33, 0.56],
    "portrait:king-arthur:merlin": [0.50, 0.50, 0.75],
    "portrait:medusa:harpies": [0.50, 0.50, 0.75],
}
KIND_ORDER = {"card": 0, "back": 1, "portrait": 2}
SETTINGS_DOC = {"powerOfTwoMode": "PAD_TO_POWER_OF_TWO", "paddingColor": "#061623 a0", "mipGen": "TMGS_SIMPLE_AVERAGE",
                "filter": "TF_TRILINEAR", "compression": "TC_BC7", "lodGroup": "TEXTUREGROUP_UI", "srgb": True,
                "neverStream": True, "address": "TA_CLAMP"}


# ---------------------------------------------------------------------------------------------------- plain helpers
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def pow2(n: int) -> int:
    p = 1
    while p < n:
        p <<= 1
    return p


def us(slug: str) -> str:
    return slug.replace("-", "_")


def derived_root(arg: str | None) -> Path:
    for cand in (arg, os.environ.get("UM_CARD_MEDIA_DERIVED")):
        if cand:
            return Path(cand)
    local = REPO / "scraped-data" / "derived" / "ue-media-v1"
    return local if local.is_dir() else MAIN_CHECKOUT / "scraped-data" / "derived" / "ue-media-v1"


def asset_for(kind: str, key: str, lang: str) -> tuple[str, str]:
    """(folder, asset name) by ВР-CP07."""
    if kind == "card":
        hero, card = key.split(":")
        return f"{ROOT_CARDS}/{us(hero)}", f"T_Card_{us(hero)}_{us(card)}_{lang.upper()}"
    if kind == "back":
        return ROOT_BACKS, f"T_CardBack_{us(key.split(':', 1)[1])}"
    parts = key.split(":")[1:]
    return ROOT_PORTRAITS, "T_Portrait_" + "_".join(us(p) for p in parts)


def plan_from_convert_report(path: Path = CONVERT_REPORT) -> list[dict]:
    """One item per CP-01 output: key, kind, lang, the derived PNG (relative), its sha256 and size, the asset."""
    rep = json.loads(path.read_text(encoding="utf-8"))
    if rep.get("schema") != "unmatched.card-media-convert/1" or not rep.get("allPixelEqual"):
        raise RuntimeError(f"{path}: not a passing CP-01 report (run tools/art/cards/convert_card_media.py)")
    items = []
    for f in rep["files"]:
        kind = {"card": "card", "back": "back", "avatar": "portrait", "sidekick": "portrait"}[f["kind"]]
        if kind == "card":
            key, lang = f["key"].rsplit(".", 1)
        else:
            key, lang = f["key"], ""
        folder, name = asset_for(kind, key, lang)
        w, h = f["size"]
        items.append({"key": key, "kind": kind, "lang": lang, "png": f["out"]["path"], "sha256": f["out"]["sha256"],
                      "src": [w, h], "pad": [pow2(w), pow2(h)], "folder": folder, "name": name,
                      "object": f"{folder}/{name}.{name}"})
    items.sort(key=lambda i: (KIND_ORDER[i["kind"]], i["key"], i["lang"]))
    return items


def build_registry(items: list[dict]) -> dict:
    entries = []
    for i in items:
        e = {"key": i["key"], "kind": i["kind"]}
        if i["lang"]:
            e["lang"] = i["lang"]
        e.update({"object": i["object"], "src": i["src"], "pad": i["pad"],
                  "uv": [round(i["src"][0] / i["pad"][0], 6), round(i["src"][1] / i["pad"][1], 6)],
                  "sha256": i["sha256"]})
        if i["kind"] == "portrait":
            e["disc"] = DISC_START[i["key"]]
            e["discSource"] = "ВР-CP01 (start; CP-07 replaces after review)"
        entries.append(e)
    return {
        "schema": REGISTRY_SCHEMA,
        "card": "CP-02",
        "generatedBy": "tools/art/cards/ue_import_card_media.py (from art/cards-v1/media-convert-report.json)",
        "decisions": ["INT-014", "ВР-CP01", "ВР-CP03", "ВР-CP07", "ВР-CP08", "ВР-51"],
        "note": ("key -> texture; uv = src / pad: the source pixels sit in the top-left of the padded texture "
                 "(padding #061623 alpha 0); cards: lang ru = RU build, en = EN build (ВР-51); portraits: disc "
                 "[cx, cy, d] in fractions of the source side. Textures are gitignored (GAP-019 / ENV-U3)."),
        "settings": SETTINGS_DOC,
        "counts": {k: sum(1 for e in entries if e["kind"] == k) for k in ("card", "back", "portrait")},
        "entries": entries,
    }


def registry_text(reg: dict) -> str:
    return json.dumps(reg, ensure_ascii=False, indent=1) + "\n"


def write_registry(reg: dict, path: Path = REGISTRY) -> bool:
    text = registry_text(reg)
    old = path.read_text(encoding="utf-8") if path.is_file() else None
    if old == text:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    return True


def select(items: list[dict], mode: str, hero: str | None) -> list[dict]:
    if mode == "all":
        return items
    if mode == "portraits":
        return [i for i in items if i["kind"] == "portrait"]
    if mode == "backs":
        return [i for i in items if i["kind"] == "back"]
    if mode == "cards":
        out = [i for i in items if i["kind"] == "card" and (hero is None or i["key"].split(":")[0] == hero)]
        if not out:
            raise RuntimeError(f"--cards {hero}: no card of that hero in the CP-01 report")
        return out
    if mode == "frames":
        return []
    raise KeyError(mode)


def verify_sources(items: list[dict], root: Path) -> list[str]:
    errors = []
    for i in items:
        p = root / i["png"]
        if not p.is_file():
            errors.append(f"{i['key']}{'.' + i['lang'] if i['lang'] else ''}: PNG missing ({p})")
        elif sha256_file(p) != i["sha256"]:
            errors.append(f"{i['key']}{'.' + i['lang'] if i['lang'] else ''}: PNG sha256 differs from the CP-01 report")
    return errors


# ---------------------------------------------------------------------------------------------------- UE side
def texture_settings() -> dict:
    tcs, mips, filt = u.TextureCompressionSettings, u.TextureMipGenSettings, u.TextureFilter
    # compression first (it decides what sRGB may be), then the rest
    return {"compression_settings": tcs.TC_BC7, "srgb": True,
            "power_of_two_mode": u.TexturePowerOfTwoSetting.PAD_TO_POWER_OF_TWO,
            "padding_color": u.Color(r=PAD_COLOR[0], g=PAD_COLOR[1], b=PAD_COLOR[2], a=PAD_COLOR[3]),
            "mip_gen_settings": mips.TMGS_SIMPLE_AVERAGE, "filter": filt.TF_TRILINEAR,
            "lod_group": u.TextureGroup.TEXTUREGROUP_UI, "never_stream": True,
            "address_x": u.TextureAddress.TA_CLAMP, "address_y": u.TextureAddress.TA_CLAMP}


def _same(a, b) -> bool:
    if isinstance(b, u.Color):
        return (a.r, a.g, a.b, a.a) == (b.r, b.g, b.b, b.a)
    return a == b


def settings_match(texture, wanted: dict) -> bool:
    return all(_same(texture.get_editor_property(k), v) for k, v in wanted.items())


def _enum(value) -> str:
    return getattr(value, "name", None) or str(value)


def describe_texture(texture) -> dict:
    c = texture.get_editor_property("padding_color")
    out = {
        "powerOfTwoMode": _enum(texture.get_editor_property("power_of_two_mode")),
        "paddingColor": "#{:02x}{:02x}{:02x} a{}".format(c.r, c.g, c.b, c.a),
        "mipGen": _enum(texture.get_editor_property("mip_gen_settings")),
        "filter": _enum(texture.get_editor_property("filter")),
        "compression": _enum(texture.get_editor_property("compression_settings")),
        "lodGroup": _enum(texture.get_editor_property("lod_group")),
        "srgb": bool(texture.get_editor_property("srgb")),
        "neverStream": bool(texture.get_editor_property("never_stream")),
        "address": [_enum(texture.get_editor_property("address_x")), _enum(texture.get_editor_property("address_y"))],
        # in the editor blueprint_get_size_* is the imported (source) size; the built size applies the build settings
        # (PAD_TO_POWER_OF_TWO) - the size of mip 0 in the pak
        "srcSize": [int(texture.blueprint_get_size_x()), int(texture.blueprint_get_size_y())],
    }
    built = texture.blueprint_get_built_texture_size()
    w, h = int(round(built.x)), int(round(built.y))
    out["size"] = [w, h]
    # full simple-average chain down to 1x1; BC7 = 16 bytes per 4x4 block. The commandlet runs with -nullrhi (no
    # GPU resource, blueprint_get_memory_size() is 0), so the pak size is computed; the C++ test
    # Unmatched.S08.CardMedia.Assets reads the real GetNumMips() of the built platform data.
    mips, total, mw, mh = 0, 0, w, h
    while True:
        mips += 1
        total += ((mw + 3) // 4) * ((mh + 3) // 4) * 16
        if mw == 1 and mh == 1:
            break
        mw, mh = max(1, mw // 2), max(1, mh // 2)
    out["mipsExpected"] = mips
    out["resourceBytesBC7"] = total
    return out


def import_one(item: dict, root: Path, force: bool) -> dict:
    eal = u.EditorAssetLibrary
    path = f"{item['folder']}/{item['name']}"
    wanted = texture_settings()
    texture = u.load_asset(path) if eal.does_asset_exist(path) else None
    if (texture is not None and not force and eal.get_metadata_tag(texture, SHA_TAG) == item["sha256"]
            and settings_match(texture, wanted)):
        return {"action": "unchanged", **describe_texture(texture)}
    action = "reimported" if texture is not None else "imported"
    task = u.AssetImportTask()
    task.filename = str(root / item["png"])
    task.destination_path = item["folder"]
    task.destination_name = item["name"]
    task.automated = True
    task.replace_existing = True
    task.save = False
    u.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    texture = u.load_asset(path)
    if texture is None or not isinstance(texture, u.Texture2D):
        raise RuntimeError(f"{item['key']}: import did not produce the texture {path}")
    for key, value in wanted.items():
        texture.set_editor_property(key, value)
    eal.set_metadata_tag(texture, SHA_TAG, item["sha256"])
    if not eal.save_loaded_asset(texture, False):
        raise RuntimeError(f"could not save {path}")
    if not settings_match(texture, wanted):
        raise RuntimeError(f"{path}: settings did not stick: {describe_texture(texture)}")
    return {"action": action, **describe_texture(texture)}


def entry_ok(d: dict, item: dict) -> list[str]:
    """Acceptance 1 per texture (read back from the asset)."""
    bad = []
    if "PAD_TO_POWER_OF_TWO" not in d["powerOfTwoMode"]:
        bad.append("powerOfTwoMode")
    if "TRILINEAR" not in d["filter"]:
        bad.append("filter")
    if "TEXTUREGROUP_UI" not in d["lodGroup"]:
        bad.append("lodGroup")
    if "BC7" not in d["compression"]:
        bad.append("compression")
    if not d["srgb"]:
        bad.append("srgb")
    if d["size"] != item["pad"]:
        bad.append(f"size {d['size']} != pad {item['pad']}")
    if d["srcSize"] != item["src"]:
        bad.append(f"source size {d['srcSize']} != {item['src']}")
    if d["mipsExpected"] <= 1 or "SIMPLE_AVERAGE" not in d["mipGen"]:
        bad.append("mips")
    if "TA_CLAMP" not in d["address"][0] or "TA_CLAMP" not in d["address"][1] or not d["neverStream"]:
        bad.append("address / neverStream")
    if d["paddingColor"] != "#061623 a0":
        bad.append("paddingColor")
    return bad


# ---------------------------------------------------------------------------------------------------- entry
def parse_args(argv: list[str]):
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true")
    g.add_argument("--portraits", action="store_true")
    g.add_argument("--backs", action="store_true")
    g.add_argument("--cards", nargs="?", const="*", default=None, metavar="HERO")
    g.add_argument("--frames", action="store_true")
    ap.add_argument("--derived", default=None)
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--check", action="store_true", help="plain Python: registry up to date and every PNG present")
    ap.add_argument("--write-registry", action="store_true", help="plain Python: write the registry only")
    args = ap.parse_args(argv)
    if args.portraits:
        args.mode, args.hero = "portraits", None
    elif args.backs:
        args.mode, args.hero = "backs", None
    elif args.cards is not None:
        args.mode, args.hero = "cards", (None if args.cards == "*" else args.cards)
    elif args.frames:
        args.mode, args.hero = "frames", None
    else:
        args.mode, args.hero = "all", None
    return args


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if not argv and os.environ.get("UM_CARD_MEDIA_ARGS"):
        argv = shlex.split(os.environ["UM_CARD_MEDIA_ARGS"])
    args = parse_args(argv)
    started = time.time()
    items = plan_from_convert_report()
    reg = build_registry(items)
    root = derived_root(args.derived)
    if args.write_registry:
        changed = write_registry(reg)
        print(f"CARD-MEDIA-REGISTRY {'written' if changed else 'unchanged'} entries={len(reg['entries'])} {REGISTRY}")
        return 0
    if args.check or u is None:
        errors = verify_sources(items, root)
        if not REGISTRY.is_file() or REGISTRY.read_text(encoding="utf-8") != registry_text(reg):
            errors.append(f"{REGISTRY}: out of date (run --write-registry)")
        for e in errors:
            print("  " + e)
        print(f"CARD-MEDIA-IMPORT check {'ok' if not errors else 'FAILED'} entries={len(items)} derived={root}")
        return 0 if not errors else 1
    # ---- inside UE
    selected = select(items, args.mode, args.hero)
    errors = verify_sources(selected, root)
    if errors:
        for e in errors:
            u.log_error("CARD-MEDIA-IMPORT " + e)
        raise RuntimeError("CARD-MEDIA-IMPORT: source verification failed - nothing imported")
    write_registry(reg)
    report_path = Path(args.report)
    previous = {}
    if report_path.is_file():
        try:
            previous = {(e["key"], e.get("lang", "")): e for e in json.loads(report_path.read_text(encoding="utf-8"))
                        .get("textures", [])}
        except ValueError:
            previous = {}
    chosen = {(i["key"], i["lang"]) for i in selected}
    textures, failures, actions = [], [], {"imported": 0, "reimported": 0, "unchanged": 0, "kept": 0}
    for item in items:
        ident = (item["key"], item["lang"])
        if ident not in chosen:
            old = previous.get(ident)
            if old and old.get("sourceSha256") == item["sha256"]:
                textures.append(old)
                actions["kept"] += 1
            continue
        try:
            d = import_one(item, root, args.force)
        except Exception as exc:  # report and continue
            failures.append(f"{item['key']} {item['lang']}: {exc}")
            continue
        actions[d.pop("action")] += 1
        bad = entry_ok(d, item)
        if bad:
            failures.append(f"{item['key']} {item['lang']}: {', '.join(bad)}")
        e = {"key": item["key"]}
        if item["lang"]:
            e["lang"] = item["lang"]
        e.update({"asset": f"{item['folder']}/{item['name']}", "source": f"scraped-data/derived/ue-media-v1/{item['png']}",
                  "sourceSha256": item["sha256"], "src": item["src"], "pad": item["pad"], "settings": d,
                  "ok": not bad})
        textures.append(e)
    textures.sort(key=lambda e: (KIND_ORDER[next(i["kind"] for i in items if i["key"] == e["key"])], e["key"],
                                 e.get("lang", "")))
    total_bytes = sum(t["settings"].get("resourceBytesBC7", 0) for t in textures)
    report = {
        "schema": REPORT_SCHEMA,
        "tool": "tools/art/cards/ue_import_card_media.py",
        "card": "CP-02",
        "status": "технически импортировано (оригинальный арт как есть; рамка и показ - CP-13 / CP-15)",
        "engine": str(u.SystemLibrary.get_engine_version()),
        "registry": "unreal/Unmatched/Config/Cards/S08CardMedia.json",
        "settingsWanted": SETTINGS_DOC,
        "count": len(textures),
        "allOk": not failures and len(textures) == len(items) and all(t.get("ok") for t in textures),
        "resourceBytesBC7Total": total_bytes,
        "resourceNote": "computed: BC7 16 B per 4x4 block, full mip chain (the -nullrhi commandlet has no GPU resource)",
        "textures": textures,
    }
    text = json.dumps(report, ensure_ascii=False, indent=1) + "\n"
    old_text = report_path.read_text(encoding="utf-8") if report_path.is_file() else None
    if old_text != text:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(text, encoding="utf-8", newline="\n")
    for f in failures:
        u.log_error("CARD-MEDIA-IMPORT " + f)
    u.log(f"CARD-MEDIA-IMPORT {'PASS' if report['allOk'] else 'FAIL'} mode={args.mode} textures={len(textures)} "
          f"imported={actions['imported']} reimported={actions['reimported']} unchanged={actions['unchanged']} "
          f"kept={actions['kept']} bytes={total_bytes} seconds={time.time() - started:.1f}")
    return 0 if not failures else 1


if __name__ == "__main__":
    code = main()
    if u is None:
        sys.exit(code)
    elif code != 0:
        raise RuntimeError("CARD-MEDIA-IMPORT failed - see the log lines above")
