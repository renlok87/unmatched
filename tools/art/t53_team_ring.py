#!/usr/bin/env python3
"""W5b-R (ART-005 board readability, decisions D-2/D-3): team rings of the art figures - content in UE.

Built ONCE through MCP in the LIVE UnrealEditor of the main checkout (127.0.0.1:8123); the .uasset files are then
copied byte-for-byte into the art worktree and force-added there (Content/ is gitignored).

    python tools/art/t53_team_ring.py plan   [--obj-dir <dir>]
    python tools/art/t53_team_ring.py build  --report <json> [--obj-dir <dir>] [--force]
    python tools/art/t53_team_ring.py verify --report <json>
    python tools/art/t53_team_ring.py copy   --report <json> --to <art worktree>/unreal/Unmatched/Content

What it makes (cooked through the existing +DirectoriesToAlwaysCook /Game/ArtTests/ARTMarkers and /Game/ArtPreview/Medusa):
  * SM_Marker_TeamRing_P1 - a flat annulus (circle) under the art figure of player 1 (seat 0 / host):
      inner keyline r 22.0-23.5 uu, fill 23.5-26.5, outer keyline 26.5-28.0 (hero size; sidekicks are scaled 0.78
      in XY by the client), top face at z = +1.2, walls down to z = +0.6 (above the zone marks, z <= 0.58, and the tile
      top z = 0: the T5.2 disc sat IN the tile plane and z-fought, act T5.2 §4.9);
  * SM_Marker_TeamRing_P2 - the same band as a hexagon (corners at 0/60/.../300 deg from +X, flats face the camera)
      measured by apothem: inner keyline 21.5-23.0, fill 23.0-26.0, outer keyline 26.0-27.0 (1.0 uu: the rule
      'outer edge + 1 uu <= the nearest zone glyph' of the plan, see RING_SPEC), with a 2.0 uu gap across each of the
      six corners (C-11 'circle vs hexagon' plus a pattern that survives a partial occlusion);
    two material slots each: 'Keyline' and 'Fill' (OBJ usemtl names);
  * MI_Marker_TeamRing_Keyline / MI_Marker_TeamRing_Fill - children of the W4-B game-layer master
    /Game/UM/Materials/M_UM_GameLayer (unlit, EyeAdaptationInverse, ISM usage); LayerColor = FLinearColor::FromSRGBColor
    of the hex (keyline #111317, fill = team.p1 #E8C06A as the asset default - the client sets the team fill per
    fighter through a MID of the fill MI);
  * MI_Medusa_P1 / MI_Medusa_P2 - the Medusa candidate MI (M_Medusa_Atlas, one TeamColor override like MI_Medusa_Blue /
    _Red) named by the absolute team (D-2) instead of own/enemy; TeamColor = the pastel of the team hue (see
    medusa_tint): a whole-figure multiply by the dark Silver #5A7F9F would black the sculpt out.

OBJ axes: UE's OBJ importer maps OBJ (x, y, z) to UE (x, -y, z) at 1 uu per unit (measured 2026-09-29 by T4.2); the
writer stores (x, -y, z) with outward right-handed winding in OBJ space (the importer mirrors Y back).
Statuses: "технически импортировано" at most; shape and palette stay "предложено" (decisions D-2/D-3, advisor).
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

MAIN_CONTENT = Path("C:/Users/ren/WebstormProjects/unmached/unmached/unreal/Unmatched/Content")
TOKENS = REPO / "docs" / "unreal" / "contracts" / "hud" / "hud-style-tokens.json"
MESH_FOLDER = "/Game/ArtTests/ARTMarkers/Meshes"
MAT_FOLDER = "/Game/ArtTests/ARTMarkers/Materials"
MEDUSA_FOLDER = "/Game/ArtPreview/Medusa/Materials"
MASTER = "/Game/UM/Materials/M_UM_GameLayer"
MEDUSA_PARENT = "/Game/ArtPreview/Medusa/Materials/M_Medusa_Atlas"
COLOR_PARAM = "LayerColor"
SCHEMA = "unmatched.t53-team-ring/1"

# Geometry (uu, hero size = figure scale 1.0). Keep in step with S08TeamRingSpec in S08BoardArt.h; the automation test
# Unmatched.S08.BoardArt.TeamRing checks the imported bounds and the clearances against these numbers.
RING_SPEC = {
    "zMin": 0.6, "zMax": 1.2,
    "p1": {"shape": "circle", "segments": 96,
           "bands": {"keylineIn": [22.0, 23.5], "fill": [23.5, 26.5], "keylineOut": [26.5, 28.0]}},
    "p2": {"shape": "hexagon", "cornersDeg": [0, 60, 120, 180, 240, 300], "measure": "apothem",
           "bands": {"keylineIn": [21.5, 23.0], "fill": [23.0, 26.0], "keylineOut": [26.0, 27.0]},
           "cornerGapUU": 2.0},
    "sidekickScaleXY": 0.78,
    "why": {
        "z": "top face +1.2 uu: above the zone marks (glyph fill top +0.58) and far from the tile top z = 0 "
             "(the T5.2 disc top was coplanar with the tile top: z-fighting)",
        "p1Outer": "28.0 + 1 uu <= 29.73 uu: the nearest zone-glyph piece (bars3, slot (+-32,+-32)) - exact piece "
                   "geometry of S08GlyphPieces, not the glyph AABB (the diamond AABB corner lies at 27.25 uu, but the "
                   "diamond itself stays 36.25 uu away)",
        "p2Outer": "hexagon apothem 27.0: the 30-degree flat passes the bars3 corner (20,22) at 1.32 uu; with the "
                   "plan's 1.5 uu outer keyline (apothem 27.5) the gap would be 0.82 uu < 1 - the plan's fallback "
                   "'outer keyline 1.0 uu' applies to P2",
        "fillInner": "P1 fill starts at 23.5 > the target arcs' outer edge 23.0 (SM_Marker_TargetRing, build_markers.py: "
                     "inner 20.9 / outer 23); P2 fill starts at apothem 23.0 = the arcs' outer edge at the flats only",
        "gaps": "P2: 2.0 uu across each corner bisector (the side trimmed 2/ (2 sin 60) = 1.1547 uu before the corner)"},
}
KEYLINE_HEX = "#111317"
# the .mtl next to each OBJ: without it the OBJ (FBX SDK) importer merges every usemtl group into one 'defaultMat'
MTL_TEXT = "newmtl Keyline\nKd 0.0056 0.0065 0.0086\n\nnewmtl Fill\nKd 0.807 0.527 0.144\n"
BAND_SLOT = {"keylineIn": "Keyline", "fill": "Fill", "keylineOut": "Keyline"}


def ring_package(slot: str) -> str:
    return f"{MESH_FOLDER}/SM_Marker_TeamRing_{slot.upper()}"


MI_KEYLINE = f"{MAT_FOLDER}/MI_Marker_TeamRing_Keyline"
MI_FILL = f"{MAT_FOLDER}/MI_Marker_TeamRing_Fill"
MI_MEDUSA = {"p1": f"{MEDUSA_FOLDER}/MI_Medusa_P1", "p2": f"{MEDUSA_FOLDER}/MI_Medusa_P2"}


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


def team_hex() -> dict:
    tok = json.loads(TOKENS.read_text(encoding="utf-8"))["colors"]
    return {"p1": tok["team.p1"]["hex"], "p2": tok["team.p2"]["hex"],
            "keyline": tok.get("mark.keyline", {}).get("hex", KEYLINE_HEX)}


def medusa_tint(hexc: str) -> list[float]:
    """Pastel of the team hue for the whole-figure multiply of the Medusa candidate (the MI_Medusa_Blue/_Red scheme):
    the linear colour normalised by its largest channel, half-way to white. #E8C06A -> (1.0, 0.827, 0.589);
    #5A7F9F -> (0.647, 0.806, 1.0) (close to the former MI_Medusa_Blue (0.72, 0.85, 1.0))."""
    lin = hex_to_linear(hexc)[:3]
    m = max(lin)
    return [round(0.5 + 0.5 * (c / m), 4) for c in lin] + [1.0]


# ------------------------------------------------------------------ geometry
def circle_band_quads(r0: float, r1: float, n: int) -> list[list[tuple[float, float]]]:
    out = []
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        out.append([(r0 * math.cos(a0), r0 * math.sin(a0)), (r1 * math.cos(a0), r1 * math.sin(a0)),
                    (r1 * math.cos(a1), r1 * math.sin(a1)), (r0 * math.cos(a1), r0 * math.sin(a1))])
    return out


def hex_side_frame(k: int) -> tuple[tuple[float, float], tuple[float, float]]:
    """Side k lies between corners at 60k and 60k+60 deg: unit normal at 60k+30, tangent +90 from the normal."""
    phi = math.radians(60 * k + 30)
    n = (math.cos(phi), math.sin(phi))
    t = (-math.sin(phi), math.cos(phi))
    return n, t


def hex_band_quads(a0: float, a1: float, gap: float) -> list[list[tuple[float, float]]]:
    trim = (gap / 2.0) / math.sin(math.radians(60))  # along the side, from the corner
    out = []
    for k in range(6):
        n, t = hex_side_frame(k)

        def p(a, u):
            return (a * n[0] + u * t[0], a * n[1] + u * t[1])
        h0 = a0 * math.tan(math.radians(30)) - trim
        h1 = a1 * math.tan(math.radians(30)) - trim
        out.append([p(a0, -h0), p(a1, -h1), p(a1, h1), p(a0, h0)])
    return out


def ring_polygons(slot: str) -> dict:
    """Top-face polygons per band (UE XY, uu) of the P1 / P2 ring."""
    spec = RING_SPEC[slot]
    out = {}
    for band, (r0, r1) in spec["bands"].items():
        out[band] = (circle_band_quads(r0, r1, spec["segments"]) if spec["shape"] == "circle"
                     else hex_band_quads(r0, r1, spec["cornerGapUU"]))
    return out


def ring_bounds(slot: str) -> dict:
    pts = [p for quads in ring_polygons(slot).values() for q in quads for p in q]
    return {"min": [round(min(p[0] for p in pts), 4), round(min(p[1] for p in pts), 4), RING_SPEC["zMin"]],
            "max": [round(max(p[0] for p in pts), 4), round(max(p[1] for p in pts), 4), RING_SPEC["zMax"]]}


def ring_obj(slot: str) -> str:
    """OBJ text: per band quad a top face (z = zMax, normal +Z) and, on the outer/inner edge of the whole band and on the
    P2 gap ends, vertical walls down to zMin (outward normals). OBJ stores UE (x, y, z) as (x, -y, z)."""
    z0, z1 = RING_SPEC["zMin"], RING_SPEC["zMax"]
    polys = ring_polygons(slot)
    groups = {"Keyline": [], "Fill": []}

    def add_face(group, pts3, want_normal):
        # pts3 in UE space; write mirrored; fix winding so the OBJ-space normal points along the mirrored want_normal
        m = [(x, -y, z) for (x, y, z) in pts3]
        wn = (want_normal[0], -want_normal[1], want_normal[2])
        a, b, c = m[0], m[1], m[2]
        u = (b[0] - a[0], b[1] - a[1], b[2] - a[2])
        v = (c[0] - b[0], c[1] - b[1], c[2] - b[2])
        nrm = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
        if nrm[0] * wn[0] + nrm[1] * wn[1] + nrm[2] * wn[2] < 0:
            m = list(reversed(m))
        ln = math.sqrt(sum(x * x for x in wn)) or 1.0
        groups[group].append((m, (wn[0] / ln, wn[1] / ln, wn[2] / ln)))

    for band, quads in polys.items():
        group = BAND_SLOT[band]
        for q in quads:
            add_face(group, [(x, y, z1) for (x, y) in q], (0.0, 0.0, 1.0))
    # walls: inner edge of keylineIn, outer edge of keylineOut (both groups 'Keyline'); P2 gap ends on every band
    def edge_wall(p, q, group):
        mx, my = (p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0
        dx, dy = q[0] - p[0], q[1] - p[1]
        n = (dy, -dx)
        return n, [(p[0], p[1], z1), (q[0], q[1], z1), (q[0], q[1], z0), (p[0], p[1], z0)], (mx, my)

    for q in polys["keylineIn"]:
        n, pts, mid = edge_wall(q[3], q[0], "Keyline")  # inner edge runs q[0]->q[3]
        if n[0] * mid[0] + n[1] * mid[1] > 0:  # inner wall faces the centre
            n = (-n[0], -n[1])
        add_face("Keyline", pts, (n[0], n[1], 0.0))
    for q in polys["keylineOut"]:
        n, pts, mid = edge_wall(q[1], q[2], "Keyline")
        if n[0] * mid[0] + n[1] * mid[1] < 0:  # outer wall faces away from the centre
            n = (-n[0], -n[1])
        add_face("Keyline", pts, (n[0], n[1], 0.0))
    if RING_SPEC[slot]["shape"] == "hexagon":
        for band, quads in polys.items():
            for k, q in enumerate(quads):
                _, t = hex_side_frame(k)
                for (p, r, sgn) in ((q[0], q[1], -1.0), (q[3], q[2], 1.0)):
                    add_face(BAND_SLOT[band], [(p[0], p[1], z1), (r[0], r[1], z1), (r[0], r[1], z0), (p[0], p[1], z0)],
                             (sgn * t[0], sgn * t[1], 0.0))
    lines = [f"# {ring_package(slot)} - W5b-R team ring {slot.upper()} ({RING_SPEC[slot]['shape']}); "
             "tools/art/t53_team_ring.py",
             # without an .mtl the OBJ (FBX SDK) importer merges every usemtl group into one 'defaultMat' slot
             f"mtllib SM_Marker_TeamRing_{slot.upper()}.mtl", f"o SM_Marker_TeamRing_{slot.upper()}", "s off"]
    verts, uvs, normals, faces = [], [], [], []
    for group in ("Keyline", "Fill"):
        faces.append(("usemtl", group))
        for pts, n in groups[group]:
            base = len(verts)
            verts += pts
            uvs += [(0.5 + p[0] / 60.0, 0.5 + p[1] / 60.0) for p in pts]
            normals.append(n)
            faces.append(("f", [base + i for i in range(len(pts))], len(normals) - 1))
    lines += ["v %.6f %.6f %.6f" % p for p in verts]
    lines += ["vt %.6f %.6f" % uv for uv in uvs]
    lines += ["vn %.6f %.6f %.6f" % n for n in normals]
    for f in faces:
        if f[0] == "usemtl":
            lines.append("usemtl " + f[1])
        else:
            lines.append("f " + " ".join("%d/%d/%d" % (k + 1, k + 1, f[2] + 1) for k in f[1]))
    return "\n".join(lines) + "\n"


def triangle_count(slot: str) -> int:
    text = ring_obj(slot)
    return sum(len(ln.split()) - 3 for ln in text.splitlines() if ln.startswith("f "))


def write_objs(obj_dir: Path) -> dict:
    obj_dir.mkdir(parents=True, exist_ok=True)
    out = {}
    for slot in ("p1", "p2"):
        p = obj_dir / f"SM_Marker_TeamRing_{slot.upper()}.obj"
        p.write_bytes(ring_obj(slot).encode("ascii"))
        (obj_dir / f"SM_Marker_TeamRing_{slot.upper()}.mtl").write_bytes(
            MTL_TEXT.encode("ascii"))
        out[slot] = {"file": p.name, "sha256": sha256_file(p), "triangles": triangle_count(slot),
                     "expectedBounds": ring_bounds(slot)}
    return out


def plan() -> dict:
    hexes = team_hex()
    return {"rings": {s: {"package": ring_package(s), "spec": RING_SPEC[s], "bounds": ring_bounds(s),
                          "triangles": triangle_count(s)} for s in ("p1", "p2")},
            "zRange": [RING_SPEC["zMin"], RING_SPEC["zMax"]], "why": RING_SPEC["why"],
            "materialInstances": [
                {"package": MI_KEYLINE, "parent": MASTER, "hex": hexes["keyline"], "linear": hex_to_linear(hexes["keyline"])},
                {"package": MI_FILL, "parent": MASTER, "hex": hexes["p1"], "linear": hex_to_linear(hexes["p1"]),
                 "note": "asset default = team.p1; the client sets the fill per fighter (MID, FromSRGBColor of the token)"}],
            "medusa": [{"package": MI_MEDUSA[s], "parent": MEDUSA_PARENT, "team": s.upper(), "hex": hexes[s],
                        "TeamColor": medusa_tint(hexes[s])} for s in ("p1", "p2")],
            "tokens": hexes}


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


def owned_packages(p: dict) -> list[str]:
    return ([r["package"] for r in p["rings"].values()] + [m["package"] for m in p["materialInstances"]]
            + [m["package"] for m in p["medusa"]])


def cmd_build(a) -> int:
    p = plan()
    objs = write_objs(Path(a.obj_dir))
    live = Live()
    owned = owned_packages(p)
    dirty = [pk for pk in owned if live.exists(pk) and live.dirty(pk)]
    if dirty:
        raise SystemExit(f"REFUSED: packages this script would save have unsaved editor changes: {dirty}")
    master = live.props(MASTER, ["ShadingModel", "bUsedWithInstancedStaticMeshes"])
    if master.get("ShadingModel") != "MSM_Unlit" or not master.get("bUsedWithInstancedStaticMeshes"):
        raise SystemExit(f"REFUSED: {MASTER} is not the unlit ISM game-layer master: {master}")
    rep = {"schema": SCHEMA, "tool": "tools/art/t53_team_ring.py build",
           "startedUtc": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
           "editor": "live UnrealEditor of the main checkout via MCP 127.0.0.1:8123",
           "currentLevel": live.call("scene", "get_current_level"), "plan": p, "obj": objs, "actions": []}
    for folder in (MESH_FOLDER, MAT_FOLDER):
        if not live.exists(folder):
            live.call("asset", "create_folder", {"path": folder})
            rep["actions"].append({"createFolder": folder})
    # material instances (created or re-coloured in place)
    for m in p["materialInstances"]:
        pkg = m["package"]
        created = not live.exists(pkg)
        if created:
            live.call("instance", "create", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": pkg.rsplit("/", 1)[1],
                                             "parent": ref(m["parent"])})
        live.call("instance", "set_vector_parameter", {"instance": ref(pkg), "name": COLOR_PARAM,
                                                       "value": dict(zip("rgba", m["linear"]))})
        rep["actions"].append({"materialInstance": pkg, "created": created, "LayerColor": m["linear"], "hex": m["hex"]})
    for m in p["medusa"]:
        pkg = m["package"]
        created = not live.exists(pkg)
        if created:
            live.call("instance", "create", {"folder_path": pkg.rsplit("/", 1)[0], "asset_name": pkg.rsplit("/", 1)[1],
                                             "parent": ref(m["parent"])})
        live.call("instance", "set_vector_parameter", {"instance": ref(pkg), "name": "TeamColor",
                                                       "value": dict(zip("rgba", m["TeamColor"]))})
        rep["actions"].append({"medusaMI": pkg, "created": created, "TeamColor": m["TeamColor"], "teamHex": m["hex"]})
    # ring meshes
    for slot, r in p["rings"].items():
        pkg = r["package"]
        name = pkg.rsplit("/", 1)[1]
        deleted = None
        if live.exists(pkg):
            if not a.force:
                rep["actions"].append({"ringMesh": pkg, "imported": False, "reason": "exists (use --force)"})
                continue
            refs = live.call("asset", "get_referencers", {"asset_path": pkg}) or []
            if refs:
                raise SystemExit(f"REFUSED: {pkg} is referenced by {refs}")
            deleted = live.call("asset", "delete", {"path": pkg})
        src = (Path(a.obj_dir) / f"{name}.obj").resolve().as_posix()
        res = live.call("static", "import_file", {"folder_path": MESH_FOLDER, "asset_name": name, "source_file": src,
                                                  "import_materials": False, "import_textures": False,
                                                  "combine_meshes": True})
        mesh = ref(pkg)
        live.call("static", "remove_collisions", {"mesh": mesh})
        if live.call("static", "is_nanite_enabled", {"mesh": mesh}):
            live.call("static", "set_nanite_enabled", {"mesh": mesh, "enabled": False})
        slots = live.call("static", "get_material_slots", {"mesh": mesh}) or []
        assigned = {}
        for s in slots:
            mi = MI_FILL if "fill" in s.lower() else MI_KEYLINE
            live.call("static", "set_material", {"mesh": mesh, "slot_name": s, "material": ref(mi)})
            assigned[s] = mi
        rep["actions"].append({"ringMesh": pkg, "imported": True, "deletedFirst": deleted, "source": src,
                               "result": res, "slots": slots, "assigned": assigned})
    to_save = [pk for pk in owned if live.exists(pk) and live.dirty(pk)]
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

    def file_row(pkg):
        f = package_file(content_root, pkg)
        return {"path": f.as_posix(), "sha256": sha256_file(f) if f.is_file() else None,
                "bytes": f.stat().st_size if f.is_file() else None}
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
                failures.append(f"{pkg}: parent {parent}")
        else:
            failures.append(f"{pkg}: missing")
        row["file"] = file_row(pkg)
        assets[pkg] = row
    for m in p["medusa"]:
        pkg = m["package"]
        row = {"exists": live.exists(pkg)}
        if row["exists"]:
            got = live.call("instance", "get_vector_parameter", {"instance": ref(pkg), "name": "TeamColor"})
            parent = live.props(pkg, ["Parent"]).get("Parent")
            row.update({"TeamColor": got, "parent": parent})
            vals = [got.get(k) for k in "rgba"] if isinstance(got, dict) else None
            if not vals or any(abs(float(x) - float(y)) > 1e-4 for x, y in zip(vals, m["TeamColor"])):
                failures.append(f"{pkg}: TeamColor {got} != {m['TeamColor']}")
            if not parent or "M_Medusa_Atlas" not in json.dumps(parent):
                failures.append(f"{pkg}: parent {parent}")
        else:
            failures.append(f"{pkg}: missing")
        row["file"] = file_row(pkg)
        assets[pkg] = row
    for slot, r in p["rings"].items():
        pkg = r["package"]
        row = {"exists": live.exists(pkg)}
        if row["exists"]:
            mesh = ref(pkg)
            b = live.call("static", "get_bounds", {"mesh": mesh})
            slots = live.call("static", "get_material_slots", {"mesh": mesh}) or []
            row.update({"bounds": b, "triangles": live.call("static", "get_triangle_count", {"mesh": mesh}),
                        "nanite": live.call("static", "is_nanite_enabled", {"mesh": mesh}), "slots": slots,
                        "materials": {s: live.call("static", "get_material", {"mesh": mesh, "slot_name": s})
                                      for s in slots}})
            exp = r["bounds"]
            got = [[b["min"][k] for k in "xyz"], [b["max"][k] for k in "xyz"]]
            err = max(abs(got[i][j] - [exp["min"], exp["max"]][i][j]) for i in range(2) for j in range(3))
            row["boundsMaxError"] = round(err, 5)
            if err > 0.02:
                failures.append(f"{pkg}: bounds {got} != expected {exp}")
            if row["triangles"] != r["triangles"]:
                failures.append(f"{pkg}: {row['triangles']} triangles != {r['triangles']}")
            if row["nanite"]:
                failures.append(f"{pkg}: Nanite enabled")
            if sorted(s.lower() for s in slots) != ["fill", "keyline"]:
                failures.append(f"{pkg}: material slots {slots} != Fill + Keyline")
        else:
            failures.append(f"{pkg}: missing")
        row["file"] = file_row(pkg)
        assets[pkg] = row
    return {"ok": not failures, "failures": failures, "assets": assets}


def cmd_verify(a) -> int:
    live = Live()
    res = verify(live, plan(), Path(a.content))
    rep = json.loads(Path(a.report).read_text(encoding="utf-8")) if Path(a.report).is_file() else {"schema": SCHEMA}
    rep["reverify"] = dict(res, atUtc=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat())
    write_json(Path(a.report), rep)
    print(json.dumps({"ok": res["ok"], "failures": res["failures"]}, ensure_ascii=False))
    return 0 if res["ok"] else 1


def cmd_copy(a) -> int:
    rep = json.loads(Path(a.report).read_text(encoding="utf-8"))
    src_root, dst_root = Path(a.content), Path(a.to)
    assets = (rep.get("reverify") or rep["verify"])["assets"]
    copied, bad = [], []
    for pkg, row in sorted(assets.items()):
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
    p = plan()
    if a.obj_dir:
        p["obj"] = write_objs(Path(a.obj_dir))
    print(json.dumps(p, ensure_ascii=False, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "build", "verify", "copy"):
        s = sub.add_parser(name)
        s.add_argument("--content", default=str(MAIN_CONTENT), help="Content dir of the editor project (main checkout)")
        if name != "plan":
            s.add_argument("--report", required=True)
        if name in ("plan", "build"):
            s.add_argument("--obj-dir", default=None if name == "plan" else "C:/tmp/w5br/obj")
        if name == "build":
            s.add_argument("--force", action="store_true")
        if name == "copy":
            s.add_argument("--to", required=True)
    a = ap.parse_args(argv)
    return {"plan": cmd_plan, "build": cmd_build, "verify": cmd_verify, "copy": cmd_copy}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
