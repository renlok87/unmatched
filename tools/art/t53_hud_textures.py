#!/usr/bin/env python3
"""W5b-R (decisions D-3/D-5): exact-size UI textures of the art HUD, imported through MCP in the LIVE editor of the main
checkout, then copied byte-for-byte into the art worktree (Content/ is gitignored: git add -f).

    python tools/art/t53_hud_textures.py build --report <json>
    python tools/art/t53_hud_textures.py copy  --report <json> --to <art worktree>/unreal/Unmatched/Content

Textures (/Game/ArtTests/ARTMarkers/Textures, cooked via +DirectoriesToAlwaysCook /Game/ArtTests/ARTMarkers):
  * T_UI_Action_AttackToken_24/32/48 - the target token of D-5 (tools/art/art004_hud_t22.py tokens);
  * T_UI_TeamShape_Circle_12 / T_UI_TeamShape_Hex_12 - the team chips of D-3 (white shape, alpha; tinted in the UI).
Settings as the T2.2 icons (tools/art/art004_hud_icon_import.py): UserInterface2D (TC_EditorIcon), no mips, UI LOD
group, sRGB, bilinear, never stream - drawn 1:1 in pixels. The T2.2 importer ran under UnrealEditor-Cmd of the art
worktree; this one uses the live editor (MCP TextureTools.import_file + ObjectTools.set_properties) so the main and the
art checkout carry the same bytes (the plan of W5b-R, step 3). Status: технически импортировано at most.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import t53_team_ring as R  # noqa: E402  (Live, ref, sha256_file, package_file, write_json)

REPO = R.REPO
FOLDER = "/Game/ArtTests/ARTMarkers/Textures"
TOKENS = REPO / "art" / "imagegen" / "mvp-v1" / "ui" / "actions" / "sized" / "token-manifest.json"
SHAPES = REPO / "art" / "imagegen" / "mvp-v1" / "ui" / "team" / "team-shapes-manifest.json"
SETTINGS = {"CompressionSettings": "TC_EditorIcon", "MipGenSettings": "TMGS_NoMipmaps", "LODGroup": "TEXTUREGROUP_UI",
            "SRGB": True, "Filter": "TF_Bilinear", "NeverStream": True}


def plan() -> list[dict]:
    out = []
    for o in json.loads(TOKENS.read_text(encoding="utf-8"))["outputs"]:
        out.append({"package": o["ueAsset"], "source": REPO / o["path"], "sourceSha256": o["sha256"], "size": o["size"]})
    for o in json.loads(SHAPES.read_text(encoding="utf-8"))["outputs"]:
        out.append({"package": o["ueAsset"], "source": REPO / o["path"], "sourceSha256": o["sha256"], "size": o["size"]})
    return out


def cmd_build(a) -> int:
    items = plan()
    live = R.Live()
    owned = [i["package"] for i in items]
    dirty = [pk for pk in owned if live.exists(pk) and live.dirty(pk)]
    if dirty:
        raise SystemExit(f"REFUSED: unsaved editor changes on {dirty}")
    rep = {"schema": "unmatched.w5br-hud-textures/1", "tool": "tools/art/t53_hud_textures.py build",
           "startedUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "editor": "live UnrealEditor of the main checkout via MCP 127.0.0.1:8123", "settings": SETTINGS,
           "status": "технически импортировано (концепт; не художественно принят)", "textures": []}
    for it in items:
        src = Path(it["source"])
        if R.sha256_file(src) != it["sourceSha256"]:
            raise SystemExit(f"REFUSED: {src} differs from its manifest")
        pkg = it["package"]
        name = pkg.rsplit("/", 1)[1]
        existed = live.exists(pkg)
        if existed:
            if not a.force:
                rep["textures"].append({"package": pkg, "imported": False, "reason": "exists (use --force)"})
                continue
            refs = live.call("asset", "get_referencers", {"asset_path": pkg}) or []
            if refs:
                raise SystemExit(f"REFUSED: {pkg} is referenced by {refs}")
            live.call("asset", "delete", {"path": pkg})
        res = live.call("texture", "import_file", {"folder_path": FOLDER, "asset_name": name,
                                                   "source_file": src.resolve().as_posix()})
        live.call("object", "set_properties", {"instance": R.ref(pkg), "values": json.dumps(SETTINGS)})
        size = live.call("texture", "get_size", {"texture": R.ref(pkg)})
        rep["textures"].append({"package": pkg, "imported": True, "source": src.relative_to(REPO).as_posix(),
                                "sourceSha256": it["sourceSha256"], "result": res, "size": size,
                                "expectedSize": it["size"]})
    to_save = [pk for pk in owned if live.exists(pk) and live.dirty(pk)]
    saved = live.call("asset", "save_assets", {"asset_paths": to_save}) if to_save else True
    time.sleep(1.0)
    rep["saved"] = {"packages": to_save, "result": saved, "dirtyAfter": {pk: live.dirty(pk) for pk in owned}}
    failures, assets = [], {}
    for it in items:
        pkg = it["package"]
        props = live.call("object", "get_properties", {"instance": R.ref(pkg), "properties": list(SETTINGS)})
        size = live.call("texture", "get_size", {"texture": R.ref(pkg)})
        f = R.package_file(Path(a.content), pkg)
        assets[pkg] = {"properties": props, "size": size,
                       "file": {"path": f.as_posix(), "sha256": R.sha256_file(f) if f.is_file() else None,
                                "bytes": f.stat().st_size if f.is_file() else None}}
        if not size or size.get("x") != it["size"] or size.get("y") != it["size"]:
            failures.append(f"{pkg}: size {size} != {it['size']}")
        for k, v in SETTINGS.items():
            got = props.get(k)
            if (got is True or got is False) and got != v or (isinstance(v, str) and str(got) != v):
                failures.append(f"{pkg}: {k}={got} != {v}")
    rep["verify"] = {"ok": not failures, "failures": failures, "assets": assets}
    rep["finishedUtc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    R.write_json(Path(a.report), rep)
    ok = not failures and not any(rep["saved"]["dirtyAfter"].values())
    print(json.dumps({"ok": ok, "saved": len(to_save), "failures": failures}, ensure_ascii=False))
    return 0 if ok else 1


def cmd_copy(a) -> int:
    rep = json.loads(Path(a.report).read_text(encoding="utf-8"))
    copied, bad = [], []
    for pkg, row in sorted(rep["verify"]["assets"].items()):
        src, dst = R.package_file(Path(a.content), pkg), R.package_file(Path(a.to), pkg)
        want = row["file"]["sha256"]
        if not src.is_file() or R.sha256_file(src) != want:
            bad.append(f"{pkg}: main Content changed since the report")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        got = R.sha256_file(dst)
        copied.append({"package": pkg, "to": dst.as_posix(), "sha256": got, "same": got == want})
        if got != want:
            bad.append(f"{pkg}: copy mismatch")
    rep["copy"] = {"to": Path(a.to).as_posix(), "files": copied, "failures": bad,
                   "atUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
    R.write_json(Path(a.report), rep)
    print(json.dumps({"copied": len(copied), "failures": bad}, ensure_ascii=False))
    return 0 if not bad else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("build", "copy"):
        s = sub.add_parser(name)
        s.add_argument("--report", required=True)
        s.add_argument("--content", default=str(R.MAIN_CONTENT))
        if name == "build":
            s.add_argument("--force", action="store_true")
        else:
            s.add_argument("--to", required=True)
    a = ap.parse_args(argv)
    return {"build": cmd_build, "copy": cmd_copy}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
