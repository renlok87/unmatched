#!/usr/bin/env python3
"""ENV-MAPS P5c UserVariant: the user's layout variant overlays <map>.user.layout.json (-EnvLayoutVariant=user).

  python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/p5c_user_overlays.py [--check]
         [--layouts DIR] [--out DIR] [--report]

ENV-U14 NoAI rule: the two NoAI packs (Megaplant_Library, StyleHex_Studio) appear ONLY here, through their
/Game/EnvKit/UserFab/ derivatives (tools/art/env_kit/ue_import_user_fab.py, spec user-fab.json next to this script).
Everything below is computed from asset paths and technical data (the measured bounds / triangles / trunk-foot box of
user-fab.json 'measured'); no frame or texture of a NoAI asset is looked at by an agent.

What the overlays do (S08EnvLayout MergeOverlay: props / fx {remove, replace, add}; lights, ground and tray stay the
base layout's):
  marmoreal  cherry-nw / -w / -e -> SM_UserFab_YoshinoC, cherry-se -> SM_UserFab_YoshinoD (static bakes of the Megaplants
             Yoshino Cherry trees). Scale: the crown's XY area = the default variant's cherry footprint area (the default
             prop's oriented bounds, layout_check.footprint), then reduced in 4 % steps until layout_check passes for the
             prop (occlusion of the space circles at every K1 / wheel / follow camera, key-light shadows, tray, frame,
             near band). Position: the crown's bounds centre on the default crown centre, the default yaw. The petals of
             each cherry (petals-<id>, anchored) move to the new crown (bounds centre, 0.55 of the height, like
             p5c_layout_fx.crown_offset).
  sarpedon   rock-nw / -w / -sw / -ne / -se and rockwet-w / -sw -> StyleHex rocks (SM_UserFab_Stone*): the footprint area
             of the default rock, the bounds centre on the default centre, the default yaw (+ a per-rock turn), z = the
             tray top (pivots below the bounds bottom sink part of the rock into the tray like a buried boulder).
Idempotent: --check exits 1 when an overlay file differs from what this script writes or a merged layout fails
layout_check / the fx rules; --out DIR writes elsewhere (scratch). --report writes
reports/p5c-user-overlays-report.json (scales, triangles per board, layout_check summary).

Status: предложено; технически проверено only by the -EnvLayoutVariant=user trace (overlay ok, missingMeshes=0);
художественная оценка - только пользователь.
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import math
import re
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REPO = HERE.parents[4]
LAYOUTS = REPO / "unreal/Unmatched/Config/ArtBoards/EnvLayouts"
TOPOLOGY = REPO / "backend/prisma/fixtures/boards"
SPEC = HERE / "user-fab.json"
REPORT = RUN / "reports/p5c-user-overlays-report.json"
OVERLAY_SCHEMA = "unmatched.env-layout-overlay/1"
VARIANT = "user"
SHRINK = 0.96
MAX_STEPS = 25
CROWN_Z_FRAC = 0.55


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


# private module copies: install_userfab() patches this layout_check copy only (other importers keep theirs)
LC = _load("_userfab_layout_check", REPO / "tools/art/env_kit/layout_check.py")
FXG = _load("_userfab_p5c_layout_fx", HERE / "p5c_layout_fx.py")
USERFAB_PREFIX = "UserFab_"

# default prop id -> (UserFab mesh name, extra yaw turn)
PLAN = {
    "marmoreal": {"cherry-nw": ("YoshinoC", 0.0), "cherry-w": ("YoshinoC", 0.0), "cherry-e": ("YoshinoC", 0.0),
                  "cherry-se": ("YoshinoD", 0.0)},
    "sarpedon": {"rock-nw": ("StoneCluster1", 0.0), "rock-w": ("StoneLarge1", 60.0), "rock-sw": ("StoneSmall3", 30.0),
                 "rock-ne": ("StoneCluster1", 140.0), "rock-se": ("StoneSmall5", 0.0),
                 "rockwet-w": ("StoneSmall1", 0.0), "rockwet-sw": ("StoneCluster2", 0.0)},
}
# StyleHex rocks with the pivot inside the rock (bounds bottom below the pivot): lift the pivot so that only this share of
# the part below the pivot stays sunk into the tray (a buried boulder, not a half-swallowed one)
SUNK_SHARE = 0.3
TRAY_TOP_Z = -3.0


def r2(v: float) -> float:
    return round(float(v), 2)


def load_spec(path: Path = SPEC) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def install_userfab(spec: dict) -> None:
    """layout_check knows the Fab duplicates of fab-picks.json; the UserFab meshes get the same treatment (pack pivot,
    bounds x scale, 'base' trunk box, scaleRange) under the name prefix 'UserFab_' - in memory only."""
    LC.FAB_MESH_RE = re.compile(r"^/Game/EnvKit/(?:Fab|UserFab)/(Marmoreal|Sarpedon)/SM_(EnvFab|UserFab)_([A-Za-z0-9]+)$")
    orig_match = LC.FAB_MESH_RE.match

    class _Re:  # keeps group(1) = map, group(2) = the FAB key ('UserFab_<Name>' for UserFab meshes)
        @staticmethod
        def match(s):
            m = orig_match(s)
            if not m:
                return None

            class _M:
                def group(self, i):
                    if i == 1:
                        return m.group(1)
                    return (USERFAB_PREFIX + m.group(3)) if m.group(2) == "UserFab" else m.group(3)
            return _M()
    LC.FAB_MESH_RE = _Re()
    for name, e in spec["meshes"].items():
        ms = e.get("measured")
        if not ms:
            continue
        LC.FAB[USERFAB_PREFIX + name] = {"map": e["map"], "bboxMin": ms["bboxMin"], "bboxMax": ms["bboxMax"],
                                         "base": ms.get("base"), "scaleRange": e["scaleRange"], "tris": ms["tris"],
                                         "kind": e["kind"]}


def userfab_dest(spec: dict, name: str) -> str:
    return spec["meshes"][name]["dest"]


def merge(base: dict, overlay: dict) -> dict:
    """Python twin of S08EnvLayout MergeOverlay (props then fx; fx anchored on a removed prop go with it)."""
    out = copy.deepcopy(base)
    for fixed in ("lights", "ground", "tray", "apron"):
        if fixed in overlay:
            raise ValueError(f"overlay cannot change '{fixed}'")
    removed_props = []
    for section, fields in (("props", ("mesh", "loc", "yawDeg", "scale", "castShadow")),
                            ("fx", ("system", "anchor", "loc", "yawDeg", "scale", "seed", "warmupS", "enabled", "user"))):
        ops = overlay.get(section, {})
        items = out.get(section, [])
        if section == "fx" and removed_props:
            items = [f for f in items if f.get("anchor") not in removed_props]
        for rid in ops.get("remove", []):
            idx = [i for i, x in enumerate(items) if x["id"] == rid]
            if not idx:
                raise ValueError(f"{section}.remove: {rid} not in the base")
            items.pop(idx[0])
            if section == "props":
                removed_props.append(rid)
        for rep in ops.get("replace", []):
            idx = [i for i, x in enumerate(items) if x["id"] == rep["id"]]
            if not idx:
                raise ValueError(f"{section}.replace: {rep['id']} not in the base")
            for k, v in rep.items():
                if k == "id":
                    continue
                if k not in fields:
                    raise ValueError(f"{section}.replace {rep['id']}: field {k} cannot be replaced")
                items[idx[0]][k] = v
        for add in ops.get("add", []):
            if any(x["id"] == add["id"] for x in items):
                raise ValueError(f"{section}.add: {add['id']} exists")
            items.append(add)
        out[section] = items
    return out


def _centre(fp) -> tuple[float, float]:
    lo, hi = fp.min(0), fp.max(0)
    return (float(lo[0] + hi[0]) / 2, float(lo[1] + hi[1]) / 2)


def place(default: dict, ms: dict, scale: float, yaw: float) -> list[float]:
    """loc that puts the mesh's bounds centre (x, y) on the default prop's footprint centre; z = the tray top, lifted
    for a pivot inside the mesh (SUNK_SHARE of the part below the pivot stays in the tray)."""
    lo, hi = ms["bboxMin"], ms["bboxMax"]
    cx, cy = (lo[0] + hi[0]) / 2 * scale, (lo[1] + hi[1]) / 2 * scale
    a = math.radians(yaw)
    tx, ty = _centre(LC.footprint(default))
    z = float(default["loc"][2])
    if lo[2] * scale < -1.0:
        z = TRAY_TOP_Z + (-lo[2] * scale) * (1.0 - SUNK_SHARE)
    return [r2(tx - (cx * math.cos(a) - cy * math.sin(a))), r2(ty - (cx * math.sin(a) + cy * math.cos(a))), r2(z)]


def lifted_base_overlaps(layout: dict, ids: list[str]) -> list[str]:
    """layout_check skips the base-overlap check 5 for Fab props above the tray top ('mounted'); the lifted rocks get it
    here: their base footprint must not overlap any other prop's base footprint (crowns / mounted props excepted)."""
    err = []
    props = {p["id"]: p for p in layout["props"]}
    for pid in ids:
        p = props[pid]
        if not LC.is_mounted(p):
            continue
        a = LC.footprint(p, base=True)
        for q in layout["props"]:
            if q["id"] == pid or (LC.is_mounted(q) and q["id"] not in ids):
                continue
            if LC.poly_clearance(a, LC.footprint(q, base=True)) < 0:
                err.append(f"prop {pid}: base footprint overlaps prop {q['id']} (lifted rock, check 5)")
    return err


def area_scale(default: dict, ms: dict) -> float:
    fp = LC.footprint(default)
    dx = float(math.dist(fp[0], fp[1]))
    dy = float(math.dist(fp[1], fp[2]))
    lo, hi = ms["bboxMin"], ms["bboxMax"]
    return math.sqrt(dx * dy / ((hi[0] - lo[0]) * (hi[1] - lo[1])))


def petals_offset(ms: dict, scale: float) -> list[float]:
    lo, hi = ms["bboxMin"], ms["bboxMax"]
    return [r2((lo[0] + hi[0]) / 2 * scale), r2((lo[1] + hi[1]) / 2 * scale),
            r2((lo[2] + CROWN_Z_FRAC * (hi[2] - lo[2])) * scale)]


def run_lc(key: str, layout: dict) -> dict:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / f"{key}.layout.json"
        p.write_text(json.dumps(layout, ensure_ascii=False), encoding="utf-8")
        return LC.check(key, p, TOPOLOGY / f"{key}.topology.json")


def prop_errors(res: dict, pid: str) -> list[str]:
    return [e for e in res["errors"] if f"prop {pid}:" in e or f"prop {pid} " in e]


def build(key: str, base: dict, spec: dict) -> tuple[dict, dict]:
    """(overlay, info) for one map."""
    props = {p["id"]: p for p in base["props"]}
    plan = PLAN[key]
    reps, fx_reps, info = [], [], {}
    for pid, (name, turn) in plan.items():
        d = props[pid]
        ms = spec["meshes"][name]["measured"]
        lo_s, hi_s = spec["meshes"][name]["scaleRange"]
        s = min(max(area_scale(d, ms), lo_s), hi_s)
        yaw = float(d["yawDeg"]) + turn
        reps.append({"id": pid, "mesh": userfab_dest(spec, name), "loc": place(d, ms, s, yaw), "yawDeg": yaw,
                     "scale": round(s, 3)})
        info[pid] = {"mesh": name, "areaScale": round(s, 3)}
    overlay = {"schema": OVERLAY_SCHEMA, "map": key, "variant": VARIANT, "boardId": base["boardId"],
               "props": {"replace": reps}}
    # shrink each replaced prop until layout_check has nothing against it (scale only; position follows the centre)
    for _ in range(MAX_STEPS):
        merged = merge(base, overlay)
        res = run_lc(key, merged)
        res["errors"] += lifted_base_overlaps(merged, [r["id"] for r in overlay["props"]["replace"]])
        bad = [r for r in overlay["props"]["replace"] if prop_errors(res, r["id"])]
        if not bad:
            break
        for r in bad:
            name = plan[r["id"]][0]
            ms = spec["meshes"][name]["measured"]
            lo_s = spec["meshes"][name]["scaleRange"][0]
            s = max(round(r["scale"] * SHRINK, 3), lo_s)
            r["scale"] = s
            r["loc"] = place(props[r["id"]], ms, s, r["yawDeg"])
    for r in overlay["props"]["replace"]:
        info[r["id"]]["scale"] = r["scale"]
        ms = spec["meshes"][plan[r["id"]][0]]["measured"]
        info[r["id"]]["sizeUU"] = [r2((ms["bboxMax"][i] - ms["bboxMin"][i]) * r["scale"]) for i in range(3)]
    if key == "marmoreal":
        fx_ids = {f["id"] for f in base.get("fx", [])}
        for r in overlay["props"]["replace"]:
            fid = f"petals-{r['id']}"
            if fid in fx_ids:
                ms = spec["meshes"][plan[r["id"]][0]]["measured"]
                fx_reps.append({"id": fid, "loc": petals_offset(ms, r["scale"])})
        if fx_reps:
            overlay["fx"] = {"replace": fx_reps}
    overlay["notes"] = ("ENV-MAPS P5c UserVariant (-EnvLayoutVariant=user), written by "
                        "art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/p5c_user_overlays.py. "
                        "NoAI (ENV-U14): the meshes are /Game/EnvKit/UserFab derivatives of Megaplant_Library / "
                        "StyleHex_Studio (tools/art/env_kit/ue_import_user_fab.py) - only in this overlay, never in "
                        f"{key}.layout.json; frames with them are for the user only, no agent looks at them.")
    return overlay, info


def validate(key: str, base: dict, overlay: dict, spec: dict) -> tuple[list[str], list[str], dict]:
    merged = merge(base, overlay)
    res = run_lc(key, merged)
    err = list(res["errors"]) + lifted_base_overlaps(merged, [p["id"] for p in overlay["props"].get("replace", [])])
    warn = list(res["warnings"])
    for op in ("replace", "add"):
        for p in overlay.get("props", {}).get(op, []):
            mesh = p.get("mesh", "")
            if mesh and not mesh.startswith("/Game/EnvKit/UserFab/"):
                if mesh.split("/")[2:3] and mesh.split("/")[2] in LC.NOAI_ROOTS:
                    err.append(f"{key}/{p['id']}: raw NoAI pack path {mesh}")
    f_err, f_warn, f_info = FXG.check_fx(key, merged, merged.get("fx", []))
    err += f_err
    warn += f_warn
    tr = LC.tris_report(merged)
    return err, warn, {"tris": tr["total"], "userFabTris": sum(v["tris"] for k, v in tr["perMesh"].items()
                                                               if k.startswith(LC.FAB_PREFIX + USERFAB_PREFIX)),
                       "props": len(merged["props"]), "fx": f_info["fx"], "particles": f_info["particlesEstimate"],
                       "lcWarnings": len(res["warnings"])}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--layouts", default=str(LAYOUTS))
    ap.add_argument("--out", default=None)
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args(argv)
    spec = load_spec()
    missing = [n for n in {m for p in PLAN.values() for m, _ in p.values()} if not spec["meshes"][n].get("measured")]
    if missing:
        print(f"USEROVERLAY ERROR meshes without measured bounds in {SPEC.name}: {sorted(missing)} "
              f"(run ue_import_user_fab.py, then --adopt-report)")
        return 1
    install_userfab(spec)
    failed, report = False, {"schema": "unmatched.env-user-overlays-report/1", "maps": {}}
    for key in PLAN:
        base = json.loads((Path(a.layouts) / f"{key}.layout.json").read_text(encoding="utf-8"))
        overlay, info = build(key, base, spec)
        err, warn, vinfo = validate(key, base, overlay, spec)
        text = json.dumps(overlay, indent=2, ensure_ascii=False) + "\n"
        target = (Path(a.out) if a.out else Path(a.layouts)) / f"{key}.{VARIANT}.layout.json"
        cur = target.read_text(encoding="utf-8") if target.is_file() else None
        state = "unchanged" if cur == text else ("differs" if a.check else "written")
        if a.check and cur != text:
            err.append(f"{target.name} differs from the generated overlay")
        if not a.check and cur != text:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(text.encode("utf-8"))
        print(f"USEROVERLAY {key}: {state} {target.name} props={len(overlay['props']['replace'])} "
              f"fx={len(overlay.get('fx', {}).get('replace', []))} tris={vinfo['tris']} (UserFab {vinfo['userFabTris']}) "
              f"particles~{vinfo['particles']} errors={len(err)} warnings={len(warn)}")
        for pid, i in info.items():
            print(f"   {pid:<12} {i['mesh']:<14} scale {i['scale']:<6} (area {i['areaScale']}) size {i['sizeUU']}")
        for w in warn:
            print(f"   WARN  {w}")
        for e in err:
            print(f"   ERROR {e}")
        failed |= bool(err)
        report["maps"][key] = {"overlay": target.name, "props": info, "validate": vinfo, "errors": err,
                               "warnings": warn}
    if a.report:
        REPORT.parent.mkdir(parents=True, exist_ok=True)
        REPORT.write_bytes((json.dumps(report, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
    print(f"USEROVERLAY {'failed' if failed else 'ok'}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
