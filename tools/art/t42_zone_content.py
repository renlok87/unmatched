#!/usr/bin/env python3
"""Stage 3 T4.2 (ART-005): map content in UE - zone material instances and zone glyph meshes.

Built ONCE through MCP in the LIVE UnrealEditor of the main checkout (127.0.0.1:8123); the .uasset files are then
copied byte-for-byte into the art worktree and force-added there (Content/ is gitignored, rule ART005).

    python tools/art/t42_zone_content.py plan  [--profiles <json>] [--obj-dir <dir>]
    python tools/art/t42_zone_content.py build --report <json> [--obj-dir <dir>] [--force]
    python tools/art/t42_zone_content.py verify --report <json>
    python tools/art/t42_zone_content.py copy --report <json> --to <art worktree>/unreal/Unmatched/Content

What it makes (folder /Game/ArtTests/ART005/Zones, cooked through the existing
+DirectoriesToAlwaysCook=(Path="/Game/ArtTests/ART005"), no ini change):
  * MI_ART005_Zone_<Key> for every zone key of Config/ArtBoards/S08ArtBoardProfiles.json zoneStyles plus
    MI_ART005_Zone_Fallback: children of the W4-B game-layer master /Game/UM/Materials/M_UM_GameLayer (Unlit,
    EyeAdaptationInverse, ISM usage) with LayerColor = FLinearColor::FromSRGBColor(zone hex) - the same linear value
    the packaged client put into its runtime MID ('Tint' = FLinearColor(FColor), memory trap 9), so the colour on
    screen does not change; one colour rule for all masters (um_masters.hex_to_linear, AD-OPEN-39).
  * SM_ART005_ZoneGlyph_<Glyph> for the 11 glyph shapes: exactly the engine-cube pieces of S08GlyphPieces
    (S08BoardArt.cpp) merged into one static mesh with its pivot on the glyph slot centre at the mark height, so one
    instance per zone slot replaces 1-4 cube instances without a visual change. Generated here as OBJ (UE's OBJ
    importer maps OBJ (x, y, z) to UE (x, -y, z) at 1 uu per unit - measured 2026-09-29 with an asymmetric probe, so
    the writer stores (x, -y, z) with outward right-handed winding), imported with StaticMeshTools.import_file,
    collision removed, Nanite off, slot material = M_UM_GameLayer. The C++ automation test
    Unmatched.S08.BoardArt.GlyphMeshes checks each mesh's bounds against the C++ pieces.
  * M_ART005H_IronCorner_Review gets bUsedWithInstancedStaticMeshes (ART-005 T3.2 finding: the corner ISM of every art
    board drew the default material in cooked builds; client log "missing usage flag InstancedStaticMeshes").

Idempotent: existing MIs are re-parented/re-coloured in place (identity kept, references survive); a glyph mesh that
already exists is left alone unless --force (then re-imported over the same package). Only the listed packages are
saved. Statuses: "технически импортировано" at most; palette and glyph shapes stay "предложено".
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import shutil
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "tools" / "tripo-pipeline"))
sys.path.insert(0, str(REPO / "tools" / "tripo-pipeline" / "review"))
from um_masters import hex_to_linear  # noqa: E402  (FLinearColor::FromSRGBColor, the single colour rule)

PROFILES = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "S08ArtBoardProfiles.json"
MAIN_CONTENT = Path("C:/Users/ren/WebstormProjects/unmached/unmached/unreal/Unmatched/Content")
FOLDER = "/Game/ArtTests/ART005/Zones"
MASTER = "/Game/UM/Materials/M_UM_GameLayer"
IRON = "/Game/ArtTests/ART005H/Materials/M_ART005H_IronCorner_Review"
COLOR_PARAM = "LayerColor"
SCHEMA = "unmatched.t42-zone-content/1"
MARK_DEPTH = 0.004  # S08BoardArt.cpp MarkDepth (cube scale z); the pivot sits at MarkZ, so pieces are centred on z 0
# W5b-R (D-4): dark keyline under every zone glyph and stroke (S08BoardArt.cpp KeylineGrowUU / KeylineDepth)
KEYLINE_GROW_UU = 1.5
KEYLINE_DEPTH = 0.003
KEYLINE_MI = FOLDER + "/MI_ART005_Zone_Keyline"

# S08GlyphPieces (S08BoardArt.cpp): (yaw deg, offset x, offset y, scale x, scale y) per engine-cube piece, relative to
# the glyph slot centre. Keep in step with the C++; Unmatched.S08.BoardArt.GlyphMeshes compares the imported bounds.
GLYPH_PIECES = {
    "diamond": [(45.0, 0.0, 0.0, 0.18, 0.18)],
    "bar1": [(0.0, 0.0, 0.0, 0.05, 0.20)],
    "bars2": [(0.0, -6.0, 0.0, 0.05, 0.20), (0.0, 6.0, 0.0, 0.05, 0.20)],
    "bars3": [(0.0, -10.0, 0.0, 0.04, 0.20), (0.0, 0.0, 0.0, 0.04, 0.20), (0.0, 10.0, 0.0, 0.04, 0.20)],
    "hbars2": [(0.0, 0.0, -6.0, 0.20, 0.05), (0.0, 0.0, 6.0, 0.20, 0.05)],
    "square": [(0.0, 0.0, 0.0, 0.14, 0.14)],
    "cross": [(0.0, 0.0, 0.0, 0.20, 0.05), (0.0, 0.0, 0.0, 0.05, 0.20)],
    "x": [(45.0, 0.0, 0.0, 0.22, 0.05), (-45.0, 0.0, 0.0, 0.22, 0.05)],
    "tee": [(0.0, 0.0, -8.0, 0.20, 0.05), (0.0, 0.0, 2.0, 0.05, 0.16)],
    "chevron": [(-53.0, -4.5, 0.0, 0.15, 0.045), (53.0, 4.5, 0.0, 0.15, 0.045)],
    "ring": [(0.0, 0.0, -8.0, 0.20, 0.04), (0.0, 0.0, 8.0, 0.20, 0.04), (0.0, -8.0, 0.0, 0.04, 0.20),
             (0.0, 8.0, 0.0, 0.04, 0.20)],
}
GLYPH_ASSET = {"diamond": "Diamond", "bar1": "Bar1", "bars2": "Bars2", "bars3": "Bars3", "hbars2": "HBars2",
               "square": "Square", "cross": "Cross", "x": "X", "tee": "Tee", "chevron": "Chevron", "ring": "Ring"}


def camel(key: str) -> str:
    return "".join(part[:1].upper() + part[1:] for part in key.replace("_", "-").split("-") if part)


def mi_package(key: str | None) -> str:
    return f"{FOLDER}/MI_ART005_Zone_{camel(key) if key else 'Fallback'}"


def glyph_package(glyph: str) -> str:
    return f"{FOLDER}/SM_ART005_ZoneGlyph_{GLYPH_ASSET[glyph]}"


def keyline_package(glyph: str) -> str:
    return f"{FOLDER}/SM_ART005_ZoneGlyphKey_{GLYPH_ASSET[glyph]}"


def obj_path(package: str) -> str:
    return "%s.%s" % (package, package.rsplit("/", 1)[-1])


def ref(package: str) -> dict:
    return {"refPath": obj_path(package)}


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_json(p: Path, doc) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def package_file(content_root: Path, package: str) -> Path:
    assert package.startswith("/Game/")
    return content_root / (package[len("/Game/"):] + ".uasset")


# ------------------------------------------------------------------ plan (offline)
def load_profiles(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def plan(profiles: dict) -> dict:
    styles = profiles["zoneStyles"]
    mis = []
    for key in sorted(styles):
        s = styles[key]
        mis.append({"key": key, "package": mi_package(key), "hex": s["color"], "linear": hex_to_linear(s["color"]),
                    "glyph": s["glyph"], "stroke": s["stroke"]})
    fb = profiles["fallbackZoneStyle"]
    mis.append({"key": None, "package": mi_package(None), "hex": fb["color"], "linear": hex_to_linear(fb["color"]),
                "glyph": fb["glyph"], "stroke": fb["stroke"]})
    glyphs = [{"glyph": g, "package": glyph_package(g), "pieces": len(GLYPH_PIECES[g]),
               "expectedBounds": glyph_bounds(g)} for g in GLYPH_PIECES]
    return {"folder": FOLDER, "master": MASTER, "colorParameter": COLOR_PARAM, "materialInstances": mis,
            "glyphMeshes": glyphs, "ismUsageFix": [IRON]}


def piece_corners(yaw: float, ox: float, oy: float, sx: float, sy: float,
                  depth: float = MARK_DEPTH) -> list[tuple[float, float, float]]:
    """Corners of one engine cube (100 uu, centred) scaled then yawed (FRotator yaw: X toward +Y) then offset -
    UE space, pivot = glyph slot centre at the mark height."""
    c, s = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    hx, hy, hz = 50.0 * sx, 50.0 * sy, 50.0 * depth
    out = []
    for dz in (-hz, hz):
        for dy in (-hy, hy):
            for dx in (-hx, hx):
                out.append((ox + dx * c - dy * s, oy + dx * s + dy * c, dz))
    return out


def keyline_pieces(glyph: str) -> list[tuple]:
    """W5b-R (D-4): the dark keyline under a zone glyph - every cube piece grown by KEYLINE_GROW_UU on each side
    (scale + 2 x grow / 100), same yaw and offset; depth KEYLINE_DEPTH (the glyph fill is MARK_DEPTH deep around the
    same pivot, so the keyline top sits 0.05 uu under the glyph fill top). Keep in step with S08GlyphKeylinePieces."""
    g = 2.0 * KEYLINE_GROW_UU / 100.0
    return [(yaw, ox, oy, sx + g, sy + g) for (yaw, ox, oy, sx, sy) in GLYPH_PIECES[glyph]]


def glyph_bounds(glyph: str, keyline: bool = False) -> dict:
    pieces = keyline_pieces(glyph) if keyline else GLYPH_PIECES[glyph]
    depth = KEYLINE_DEPTH if keyline else MARK_DEPTH
    pts = [p for piece in pieces for p in piece_corners(*piece, depth=depth)]
    return {"min": [round(min(p[i] for p in pts), 4) for i in range(3)],
            "max": [round(max(p[i] for p in pts), 4) for i in range(3)]}


FACES = [(0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4), (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5)]
UV_QUAD = [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]


def glyph_obj(glyph: str, keyline: bool = False) -> str:
    """OBJ text: per piece 8 corners mapped UE (x, y, z) -> OBJ (x, -y, z) (the importer mirrors Y back), 6 quads with
    outward right-handed winding in OBJ space, one flat normal and a unit-square UV each (v/vt/vn). UE 5.8 reads the
    OBJ through the FBX SDK (log category FBXImport)."""
    pkg = keyline_package(glyph) if keyline else glyph_package(glyph)
    what = "keyline (pieces +%.1f uu)" % KEYLINE_GROW_UU if keyline else "merged"
    lines = [f"# {pkg} - S08GlyphPieces '{glyph}' {what} (tools/art/t42_zone_content.py)",
             f"o {pkg.rsplit('/', 1)[1]}", "s off", "usemtl ZoneGlyph"]
    verts, normals, faces = [], [], []
    for piece in (keyline_pieces(glyph) if keyline else GLYPH_PIECES[glyph]):
        base = len(verts)
        corners = [(x, -y, z) for (x, y, z) in piece_corners(*piece, depth=KEYLINE_DEPTH if keyline else MARK_DEPTH)]
        verts += corners
        cx = sum(p[0] for p in corners) / 8.0
        cy = sum(p[1] for p in corners) / 8.0
        cz = sum(p[2] for p in corners) / 8.0
        for f in FACES:
            a, b, c = (corners[f[0]], corners[f[1]], corners[f[2]])
            u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
            v = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
            n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
            fc = [sum(corners[k][i] for k in f) / 4.0 for i in range(3)]
            order = list(f)
            if n[0] * (fc[0] - cx) + n[1] * (fc[1] - cy) + n[2] * (fc[2] - cz) < 0:
                order.reverse()
                n = (-n[0], -n[1], -n[2])
            ln = math.sqrt(n[0] ** 2 + n[1] ** 2 + n[2] ** 2) or 1.0
            normals.append((n[0] / ln, n[1] / ln, n[2] / ln))
            faces.append(([base + k for k in order], len(normals) - 1))
    lines += ["v %.6f %.6f %.6f" % p for p in verts]
    # one unit square per quad (corner i -> UV_QUAD[i]): the material is unlit and ignores UVs, but without them the
    # importer builds degenerate tangent bases (MikkTSpace warnings on the first import, 2026-09-29)
    lines += ["vt %.1f %.1f" % uv for uv in UV_QUAD]
    lines += ["vn %.6f %.6f %.6f" % n for n in normals]
    lines += ["f " + " ".join("%d/%d/%d" % (k + 1, c + 1, ni + 1) for c, k in enumerate(idx)) for idx, ni in faces]
    return "\n".join(lines) + "\n"


def write_objs(obj_dir: Path) -> dict:
    obj_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for g in GLYPH_PIECES:
        p = obj_dir / f"SM_ART005_ZoneGlyph_{GLYPH_ASSET[g]}.obj"
        p.write_bytes(glyph_obj(g).encode("ascii"))
        out[g] = {"file": p.name, "sha256": sha256_file(p)}
    return out


# ------------------------------------------------------------------ live editor
class Live:
    def __init__(self):
        from ue_live import Ue
        self.ue = Ue()

    def call(self, ts, tool, args=None):
        return self.ue.call(ts, tool, args or {})

    def exists(self, package: str) -> bool:
        return bool(self.call("asset", "exists", {"path": package}))

    def dirty(self, package: str) -> bool:
        return bool(self.call("asset", "is_dirty", {"asset_path": package}))

    def props(self, package: str, names: list[str]) -> dict:
        return self.call("object", "get_properties", {"instance": ref(package), "properties": names})


def preflight(live: Live, packages: list[str]) -> dict:
    level = live.call("scene", "get_current_level")
    dirty = {p: live.dirty(p) for p in packages if live.exists(p)}
    touched_dirty = [p for p, d in dirty.items() if d]
    if touched_dirty:
        raise SystemExit(f"REFUSED: packages this script would save have unsaved editor changes: {touched_dirty}")
    master = live.props(MASTER, ["ShadingModel", "bUsedWithInstancedStaticMeshes", "BlendMode"])
    params = live.call("instance", "list_parameters", {"material": ref(MASTER)})
    if not master.get("bUsedWithInstancedStaticMeshes") or master.get("ShadingModel") != "MSM_Unlit":
        raise SystemExit(f"REFUSED: {MASTER} is not the unlit ISM game-layer master: {master}")
    if not any(p.get("name") == COLOR_PARAM and p.get("type") == "Vector" for p in params):
        raise SystemExit(f"REFUSED: {MASTER} has no vector parameter {COLOR_PARAM}: {params}")
    return {"currentLevel": level, "master": master, "masterParameters": params, "preexisting": sorted(dirty)}


def cmd_build(a) -> int:
    profiles = load_profiles(Path(a.profiles))
    p = plan(profiles)
    obj_dir = Path(a.obj_dir)
    objs = write_objs(obj_dir)
    live = Live()
    owned = [m["package"] for m in p["materialInstances"]] + [g["package"] for g in p["glyphMeshes"]] + [IRON]
    rep = {"schema": SCHEMA, "tool": "tools/art/t42_zone_content.py build",
           "startedUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "editor": "live UnrealEditor of the main checkout via MCP 127.0.0.1:8123", "plan": p, "obj": objs,
           "preflight": preflight(live, owned), "actions": []}
    if not live.exists(FOLDER):
        live.call("asset", "create_folder", {"path": FOLDER})
        rep["actions"].append({"createFolder": FOLDER})
    # material instances
    for m in p["materialInstances"]:
        pkg = m["package"]
        created = False
        if not live.exists(pkg):
            name = pkg.rsplit("/", 1)[1]
            live.call("instance", "create", {"folder_path": FOLDER, "asset_name": name, "parent": ref(MASTER)})
            created = True
        else:
            live.call("instance", "set_parent", {"instance": ref(pkg), "parent": ref(MASTER)})
        live.call("instance", "set_vector_parameter",
                  {"instance": ref(pkg), "name": COLOR_PARAM, "value": dict(zip("rgba", m["linear"]))})
        rep["actions"].append({"materialInstance": pkg, "created": created, "LayerColor": m["linear"], "hex": m["hex"]})
    # glyph meshes
    for g in p["glyphMeshes"]:
        pkg = g["package"]
        name = pkg.rsplit("/", 1)[1]
        deleted = None
        if live.exists(pkg):
            if not a.force:
                rep["actions"].append({"glyphMesh": pkg, "imported": False, "reason": "exists (use --force to re-import)"})
                continue
            # MCP import_file refuses an existing package: --force deletes the mesh first, but only while no asset
            # references it (the client reaches it by a soft path from the profile JSON, never a hard reference)
            refs = live.call("asset", "get_referencers", {"asset_path": pkg}) or []
            if refs:
                raise SystemExit(f"REFUSED: {pkg} is referenced by {refs}; delete would null those references")
            deleted = live.call("asset", "delete", {"path": pkg})
        src = (obj_dir / f"{name}.obj").resolve().as_posix()
        res = live.call("static", "import_file", {"folder_path": FOLDER, "asset_name": name, "source_file": src,
                                                  "import_materials": False, "import_textures": False,
                                                  "combine_meshes": True})
        mesh = ref(pkg)
        live.call("static", "remove_collisions", {"mesh": mesh})
        if live.call("static", "is_nanite_enabled", {"mesh": mesh}):
            live.call("static", "set_nanite_enabled", {"mesh": mesh, "enabled": False})
        slots = live.call("static", "get_material_slots", {"mesh": mesh})
        for slot in slots or []:
            live.call("static", "set_material", {"mesh": mesh, "slot_name": slot, "material": ref(MASTER)})
        rep["actions"].append({"glyphMesh": pkg, "imported": True, "deletedFirst": deleted, "source": src,
                               "result": res, "slots": slots})
    # ISM usage on the corner material (T3.2 finding)
    before = live.props(IRON, ["bUsedWithInstancedStaticMeshes"])
    if not before.get("bUsedWithInstancedStaticMeshes"):
        live.call("object", "set_properties", {"instance": ref(IRON),
                                               "values": json.dumps({"bUsedWithInstancedStaticMeshes": True})})
        live.call("material", "recompile", {"material_or_function": ref(IRON)})
    rep["actions"].append({"ismUsage": IRON, "before": before,
                           "after": live.props(IRON, ["bUsedWithInstancedStaticMeshes"])})
    to_save = [pk for pk in owned if live.dirty(pk)]
    saved = live.call("asset", "save_assets", {"asset_paths": to_save}) if to_save else True
    time.sleep(1.0)
    rep["saved"] = {"packages": to_save, "result": saved, "dirtyAfter": {pk: live.dirty(pk) for pk in owned}}
    rep["verify"] = verify(live, p, Path(a.content))
    rep["finishedUtc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    rep["mcpCalls"] = len(live.ue.calls)
    write_json(Path(a.report), rep)
    ok = rep["verify"]["ok"] and not any(rep["saved"]["dirtyAfter"].values())
    print(json.dumps({"ok": ok, "saved": len(to_save), "failures": rep["verify"]["failures"]}, ensure_ascii=False))
    return 0 if ok else 1


def verify(live: Live, p: dict, content_root: Path) -> dict:
    failures, assets = [], {}
    for m in p["materialInstances"]:
        pkg = m["package"]
        row = {"exists": live.exists(pkg)}
        if row["exists"]:
            got = live.call("instance", "get_vector_parameter", {"instance": ref(pkg), "name": COLOR_PARAM})
            parent = live.props(pkg, ["Parent"]).get("Parent")
            row.update({"LayerColor": got, "parent": parent})
            vals = [got.get(k) for k in "rgba"] if isinstance(got, dict) else None
            if not vals or any(abs(float(x) - float(y)) > 1e-5 for x, y in zip(vals, m["linear"])):
                failures.append(f"{pkg}: LayerColor {got} != {m['linear']}")
            if not parent or MASTER.rsplit("/", 1)[1] not in json.dumps(parent):
                failures.append(f"{pkg}: parent {parent} is not {MASTER}")
        else:
            failures.append(f"{pkg}: missing")
        f = package_file(content_root, pkg)
        row["file"] = {"path": f.as_posix(), "sha256": sha256_file(f) if f.is_file() else None,
                       "bytes": f.stat().st_size if f.is_file() else None}
        assets[pkg] = row
    for g in p["glyphMeshes"]:
        pkg = g["package"]
        row = {"exists": live.exists(pkg)}
        if row["exists"]:
            mesh = ref(pkg)
            b = live.call("static", "get_bounds", {"mesh": mesh})
            row.update({"bounds": b, "vertices": live.call("static", "get_vertex_count", {"mesh": mesh}),
                        "triangles": live.call("static", "get_triangle_count", {"mesh": mesh}),
                        "nanite": live.call("static", "is_nanite_enabled", {"mesh": mesh}),
                        "slots": live.call("static", "get_material_slots", {"mesh": mesh})})
            exp = g["expectedBounds"]
            got = [[b["min"][k] for k in "xyz"], [b["max"][k] for k in "xyz"]]
            err = max(abs(got[i][j] - [exp["min"], exp["max"]][i][j]) for i in range(2) for j in range(3))
            row["boundsMaxError"] = round(err, 5)
            if err > 0.01:
                failures.append(f"{pkg}: bounds {got} != expected {exp}")
            if row["triangles"] != 12 * g["pieces"]:
                failures.append(f"{pkg}: {row['triangles']} triangles != 12 x {g['pieces']} pieces")
            if row["nanite"]:
                failures.append(f"{pkg}: Nanite enabled")
        else:
            failures.append(f"{pkg}: missing")
        f = package_file(content_root, pkg)
        row["file"] = {"path": f.as_posix(), "sha256": sha256_file(f) if f.is_file() else None,
                       "bytes": f.stat().st_size if f.is_file() else None}
        assets[pkg] = row
    iron = live.props(IRON, ["bUsedWithInstancedStaticMeshes"])
    f = package_file(content_root, IRON)
    assets[IRON] = {"bUsedWithInstancedStaticMeshes": iron.get("bUsedWithInstancedStaticMeshes"),
                    "file": {"path": f.as_posix(), "sha256": sha256_file(f), "bytes": f.stat().st_size}}
    if not iron.get("bUsedWithInstancedStaticMeshes"):
        failures.append(f"{IRON}: bUsedWithInstancedStaticMeshes still false")
    return {"ok": not failures, "failures": failures, "assets": assets}


def cmd_verify(a) -> int:
    p = plan(load_profiles(Path(a.profiles)))
    live = Live()
    res = verify(live, p, Path(a.content))
    rep = json.loads(Path(a.report).read_text(encoding="utf-8")) if Path(a.report).is_file() else {"schema": SCHEMA}
    rep["reverify"] = dict(res, atUtc=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat())
    write_json(Path(a.report), rep)
    print(json.dumps({"ok": res["ok"], "failures": res["failures"]}, ensure_ascii=False))
    return 0 if res["ok"] else 1


def cmd_copy(a) -> int:
    rep = json.loads(Path(a.report).read_text(encoding="utf-8"))
    src_root, dst_root = Path(a.content), Path(a.to)
    copied, bad = [], []
    for pkg, row in sorted(rep["verify"]["assets"].items()):
        src, dst = package_file(src_root, pkg), package_file(dst_root, pkg)
        want = row["file"]["sha256"]
        if sha256_file(src) != want:
            bad.append(f"{pkg}: main Content changed since the build report")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        before = sha256_file(dst) if dst.is_file() else None
        shutil.copy2(src, dst)
        got = sha256_file(dst)
        copied.append({"package": pkg, "to": dst.as_posix(), "sha256": got, "before": before, "same": got == want})
        if got != want:
            bad.append(f"{pkg}: copy hash mismatch")
    rep["copy"] = {"to": dst_root.as_posix(), "files": copied, "failures": bad,
                   "atUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
    write_json(Path(a.report), rep)
    print(json.dumps({"copied": len(copied), "failures": bad}, ensure_ascii=False))
    return 0 if not bad else 1


# ------------------------------------------------------------------ W5b-R keylines (decision D-4)
def keyline_plan(profiles: dict) -> dict:
    kl = profiles.get("zoneKeyline") or {}
    hexc = kl.get("color", "#111317")
    return {"materialInstance": {"package": kl.get("materialInstance", KEYLINE_MI), "hex": hexc,
                                 "linear": hex_to_linear(hexc)},
            "glyphMeshes": [{"glyph": g, "package": keyline_package(g), "pieces": len(GLYPH_PIECES[g]),
                             "expectedBounds": glyph_bounds(g, keyline=True)} for g in GLYPH_PIECES],
            "growUU": KEYLINE_GROW_UU, "depth": KEYLINE_DEPTH,
            "recolor": [{"key": m["key"], "package": m["package"], "hex": m["hex"], "linear": m["linear"]}
                        for m in plan(profiles)["materialInstances"]]}


def cmd_keylines(a) -> int:
    """Keyline content of D-4 through MCP (live editor): MI_ART005_Zone_Keyline, SM_ART005_ZoneGlyphKey_<Glyph> (the
    glyph pieces grown by 1.5 uu, depth 0.3 uu, same pivot as the glyph meshes) and a re-colour of every zone MI whose
    LayerColor differs from the profile (rev 4: gray #D2D7DC -> #7F868E). Only changed packages are saved."""
    profiles = load_profiles(Path(a.profiles))
    kp = keyline_plan(profiles)
    obj_dir = Path(a.obj_dir)
    obj_dir.mkdir(parents=True, exist_ok=True)
    objs = {}
    for g in GLYPH_PIECES:
        pth = obj_dir / f"SM_ART005_ZoneGlyphKey_{GLYPH_ASSET[g]}.obj"
        pth.write_bytes(glyph_obj(g, keyline=True).encode("ascii"))
        objs[g] = {"file": pth.name, "sha256": sha256_file(pth)}
    live = Live()
    owned = ([kp["materialInstance"]["package"]] + [g["package"] for g in kp["glyphMeshes"]]
             + [m["package"] for m in kp["recolor"]])
    dirty = [pk for pk in owned if live.exists(pk) and live.dirty(pk)]
    if dirty:
        raise SystemExit(f"REFUSED: packages this script would save have unsaved editor changes: {dirty}")
    rep = {"schema": SCHEMA + "+keylines", "tool": "tools/art/t42_zone_content.py keylines",
           "startedUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "editor": "live UnrealEditor of the main checkout via MCP 127.0.0.1:8123", "plan": kp, "obj": objs,
           "currentLevel": live.call("scene", "get_current_level"), "actions": []}
    mi = kp["materialInstance"]
    if not live.exists(mi["package"]):
        live.call("instance", "create", {"folder_path": FOLDER, "asset_name": mi["package"].rsplit("/", 1)[1],
                                         "parent": ref(MASTER)})
        rep["actions"].append({"createMI": mi["package"]})
    got = live.call("instance", "get_vector_parameter", {"instance": ref(mi["package"]), "name": COLOR_PARAM})
    vals = [got.get(k) for k in "rgba"] if isinstance(got, dict) else None
    if not (vals and all(abs(float(x) - float(y)) <= 1e-5 for x, y in zip(vals, mi["linear"]))):
        # 5c-B1: set only when it differs - an unconditional set dirtied and re-saved an unchanged keyline MI
        live.call("instance", "set_vector_parameter", {"instance": ref(mi["package"]), "name": COLOR_PARAM,
                                                       "value": dict(zip("rgba", mi["linear"]))})
    for m in kp["recolor"]:
        got = live.call("instance", "get_vector_parameter", {"instance": ref(m["package"]), "name": COLOR_PARAM})
        vals = [got.get(k) for k in "rgba"] if isinstance(got, dict) else None
        if vals and all(abs(float(x) - float(y)) <= 1e-5 for x, y in zip(vals, m["linear"])):
            continue
        live.call("instance", "set_vector_parameter", {"instance": ref(m["package"]), "name": COLOR_PARAM,
                                                       "value": dict(zip("rgba", m["linear"]))})
        rep["actions"].append({"recolor": m["package"], "from": got, "to": m["linear"], "hex": m["hex"]})
    for g in kp["glyphMeshes"]:
        pkg = g["package"]
        name = pkg.rsplit("/", 1)[1]
        if live.exists(pkg):
            if not a.force:
                rep["actions"].append({"keylineMesh": pkg, "imported": False, "reason": "exists (use --force)"})
                continue
            refs = live.call("asset", "get_referencers", {"asset_path": pkg}) or []
            if refs:
                raise SystemExit(f"REFUSED: {pkg} is referenced by {refs}")
            live.call("asset", "delete", {"path": pkg})
        src = (obj_dir / f"{name}.obj").resolve().as_posix()
        res = live.call("static", "import_file", {"folder_path": FOLDER, "asset_name": name, "source_file": src,
                                                  "import_materials": False, "import_textures": False,
                                                  "combine_meshes": True})
        mesh = ref(pkg)
        live.call("static", "remove_collisions", {"mesh": mesh})
        if live.call("static", "is_nanite_enabled", {"mesh": mesh}):
            live.call("static", "set_nanite_enabled", {"mesh": mesh, "enabled": False})
        slots = live.call("static", "get_material_slots", {"mesh": mesh})
        for slot in slots or []:
            live.call("static", "set_material", {"mesh": mesh, "slot_name": slot, "material": ref(mi["package"])})
        rep["actions"].append({"keylineMesh": pkg, "imported": True, "source": src, "result": res, "slots": slots})
    to_save = [pk for pk in owned if live.exists(pk) and live.dirty(pk)]
    saved = live.call("asset", "save_assets", {"asset_paths": to_save}) if to_save else True
    time.sleep(1.0)
    rep["saved"] = {"packages": to_save, "result": saved, "dirtyAfter": {pk: live.dirty(pk) for pk in owned}}
    rep["verify"] = verify_keylines(live, profiles, Path(a.content))
    rep["finishedUtc"] = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    write_json(Path(a.report), rep)
    ok = rep["verify"]["ok"] and not any(rep["saved"]["dirtyAfter"].values())
    print(json.dumps({"ok": ok, "saved": to_save, "failures": rep["verify"]["failures"]}, ensure_ascii=False))
    return 0 if ok else 1


def verify_keylines(live: Live, profiles: dict, content_root: Path) -> dict:
    kp = keyline_plan(profiles)
    failures, assets = [], {}

    def frow(pkg):
        f = package_file(content_root, pkg)
        return {"path": f.as_posix(), "sha256": sha256_file(f) if f.is_file() else None,
                "bytes": f.stat().st_size if f.is_file() else None}
    for m in [kp["materialInstance"]] + kp["recolor"]:
        pkg = m["package"]
        got = (live.call("instance", "get_vector_parameter", {"instance": ref(pkg), "name": COLOR_PARAM})
               if live.exists(pkg) else None)
        vals = [got.get(k) for k in "rgba"] if isinstance(got, dict) else None
        if not vals or any(abs(float(x) - float(y)) > 1e-5 for x, y in zip(vals, m["linear"])):
            failures.append(f"{pkg}: LayerColor {got} != {m['linear']} ({m['hex']})")
        assets[pkg] = {"LayerColor": got, "hex": m["hex"], "file": frow(pkg)}
    for g in kp["glyphMeshes"]:
        pkg = g["package"]
        row = {"exists": live.exists(pkg)}
        if row["exists"]:
            mesh = ref(pkg)
            b = live.call("static", "get_bounds", {"mesh": mesh})
            row.update({"bounds": b, "triangles": live.call("static", "get_triangle_count", {"mesh": mesh}),
                        "nanite": live.call("static", "is_nanite_enabled", {"mesh": mesh}),
                        "slots": live.call("static", "get_material_slots", {"mesh": mesh})})
            exp = g["expectedBounds"]
            got = [[b["min"][k] for k in "xyz"], [b["max"][k] for k in "xyz"]]
            err = max(abs(got[i][j] - [exp["min"], exp["max"]][i][j]) for i in range(2) for j in range(3))
            row["boundsMaxError"] = round(err, 5)
            if err > 0.01:
                failures.append(f"{pkg}: bounds {got} != expected {exp}")
            if row["triangles"] != 12 * g["pieces"]:
                failures.append(f"{pkg}: {row['triangles']} triangles != 12 x {g['pieces']}")
            if row["nanite"]:
                failures.append(f"{pkg}: Nanite enabled")
        else:
            failures.append(f"{pkg}: missing")
        row["file"] = frow(pkg)
        assets[pkg] = row
    return {"ok": not failures, "failures": failures, "assets": assets}


def cmd_keylines_copy(a) -> int:
    """Copy the keyline packages of a keylines report (main Content -> art worktree Content), byte for byte."""
    rep = json.loads(Path(a.report).read_text(encoding="utf-8"))
    src_root, dst_root = Path(a.content), Path(a.to)
    copied, bad = [], []
    for pkg, row in sorted(rep["verify"]["assets"].items()):
        src, dst = package_file(src_root, pkg), package_file(dst_root, pkg)
        want = row["file"]["sha256"]
        if not src.is_file() or sha256_file(src) != want:
            bad.append(f"{pkg}: main Content changed since the report")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        before = sha256_file(dst) if dst.is_file() else None
        shutil.copy2(src, dst)
        got = sha256_file(dst)
        copied.append({"package": pkg, "to": dst.as_posix(), "sha256": got, "before": before, "same": got == want})
        if got != want:
            bad.append(f"{pkg}: copy hash mismatch")
    rep["copy"] = {"to": dst_root.as_posix(), "files": copied, "failures": bad,
                   "atUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()}
    write_json(Path(a.report), rep)
    print(json.dumps({"copied": len(copied), "failures": bad}, ensure_ascii=False))
    return 0 if not bad else 1


def cmd_plan(a) -> int:
    p = plan(load_profiles(Path(a.profiles)))
    if a.obj_dir:
        p["obj"] = write_objs(Path(a.obj_dir))
    print(json.dumps(p, ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "build", "verify", "copy", "keylines", "keylines-copy"):
        s = sub.add_parser(name)
        s.add_argument("--profiles", default=str(PROFILES))
        s.add_argument("--content", default=str(MAIN_CONTENT), help="Content dir of the editor project (main checkout)")
        if name != "plan":
            s.add_argument("--report", required=True)
        if name in ("plan", "build"):
            s.add_argument("--obj-dir", default=None if name == "plan" else "C:/tmp/t42/glyph-obj")
        if name == "keylines":
            s.add_argument("--obj-dir", default="C:/tmp/w5br/obj")
        if name in ("build", "keylines"):
            s.add_argument("--force", action="store_true")
        if name in ("copy", "keylines-copy"):
            s.add_argument("--to", required=True)
    a = ap.parse_args(argv)
    return {"plan": cmd_plan, "build": cmd_build, "verify": cmd_verify, "copy": cmd_copy,
            "keylines": cmd_keylines, "keylines-copy": cmd_keylines_copy}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
