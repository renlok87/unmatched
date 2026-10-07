"""ENV-MAPS P7 (ENV-U15) concept paste, track A: the env-layout overlays of the concept mode.

Writes unreal/Unmatched/Config/ArtBoards/EnvLayouts/<map>.concept.layout.json (schema unmatched.env-layout-overlay/1,
variant 'concept', S08EnvLayout MergeOverlay: props / fx {remove, replace, add}) from
  * the base layout <map>.layout.json (ids to remove; fx anchored on a removed prop go with it),
  * the spec <map>.paste.json ("details" + "layout": meshes, yaw, scale rules, fx, lights),
  * the detail positions of the design (paste_proto.detail_positions: the C0 ray through the painted pixel hitting its
    host flat of the relief proxy - the same numbers as design.json 5_elements.keep_3D_animated),
  * the measured meshes of the asset build (art/pipeline-candidates/ASSET-ENV-CONCEPT-PASTE-001/<run>/reports/
    build-report.json: lantern glow offset / height, banner cross-bar / cloth width, kit cannon barrel axis).

The concept-mode lights (design.json 4: 5 points at the true fire / lantern positions) cannot go through MergeOverlay
(it refuses a top-level 'lights' - the base light budget is protected); the profile block conceptPaste carries them
(track B: S08ArtBoardProfiles.json, with flicker; hide 'layoutLights'). The overlay's own "conceptPaste" section (the
parser ignores unknown top-level keys) only names the spec / manifest / build report and lists the reference light
points derived from the detail positions (cross-check for the profile values).

VS-5 EN-07 (ENV-U16, Marmoreal): details of kind "paint-lantern" are painted lanterns / sconces / the door that stay in
the plate (the EN-04 lantern layer baked into it): no mesh, no fx - only their world point (the C0 ray of the painted glass
on the relief proxy: ground + heightUU or the colonnade flat) goes to the overlay's conceptPaste section ("paintLanterns")
and to the light reference (conceptPaste.lights of the profile block and the anim.lanterns slots). "layout.fxRemoveBase":
true removes every base fx (the ones anchored on a removed prop go with it anyway). The fx overlay field list includes
"reducedMotion" (VS-5 EN-06).

Deterministic: the same inputs give the same bytes; `--check` compares the committed files with a fresh generation
and validates the merged layout (Python twin of MergeOverlay + the structural rules of S08EnvLayout ParseJson that
matter here: unique ids, kit roots, scale / warmup ranges, fx anchors, pivots off the painted map, light budget).

  python -B tools/art/concept_paste/cp_layout.py [--maps sarpedon,marmoreal]          # write
  python -B tools/art/concept_paste/cp_layout.py --check [--maps ...]                 # compare + validate
"""
from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import cp_common as C  # noqa: E402
import paste_proto as pp  # noqa: E402

REPO = C.REPO
LAYOUTS = REPO / "unreal" / "Unmatched" / "Config" / "ArtBoards" / "EnvLayouts"
BUILD_REPORT = REPO / "art" / "pipeline-candidates" / "ASSET-ENV-CONCEPT-PASTE-001" / "20261001-p7" / "reports" / "build-report.json"
OVERLAY_SCHEMA = "unmatched.env-layout-overlay/1"
KIT_ROOT = "/Game/EnvKit/"
NOAI_ROOTS = ("Megaplant_Library", "StyleHex_Studio")  # ENV-U14: never in the concept overlays
MAX_POINT_LIGHTS = 6
PROFILE_POINTS = 1  # the night profiles keep one cool moon-pool (S08ArtBoardProfiles.json rev 7 / 9)


def r2(v: float) -> float:
    return round(float(v) + 0.0, 2)


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def seed_of(fid: str) -> int:
    return zlib.crc32(fid.encode("utf-8")) & 0x7FFFFFFF


def rot_yaw(v, yaw_deg: float) -> np.ndarray:
    a = math.radians(yaw_deg)
    x, y, z = (float(c) for c in v)
    return np.array([x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z])


def export_of(report: dict, name: str) -> dict:
    for e in report["exports"]:
        if e["name"] == name:
            return e
    raise KeyError(f"{name} not in the build report")


def ship_yaw(spec: dict) -> float:
    """Yaw whose local +X is the ship flat's normal towards C0 (local Y along the hull line)."""
    cam = C.concept_cam()
    zone = next(z for z in spec["geometry"]["planeZones"] if z["id"] == spec["layout"]["banner"]["hostZone"])
    P0, n = pp.zone_plane(cam, zone, spec["geometry"]["groundZ"])
    return math.degrees(math.atan2(n[1], n[0]))


def banner_hang_local(spec: dict) -> list[float]:
    """P7c: the C0 screen-down direction (-C0 up) in the banner's yaw frame (local X = the ship flat's normal to C0,
    local Y along the rail): the hang of SM_EnvCP_BannerCloth (cp-assets-params.json bannerCloth.hangLocal)."""
    yaw = math.radians(round(ship_yaw(spec), 2))
    d = -C.concept_cam().up
    xl = np.array([math.cos(yaw), math.sin(yaw), 0.0])
    yl = np.array([-math.sin(yaw), math.cos(yaw), 0.0])
    return [round(float(d @ xl), 4), round(float(d @ yl), 4), round(float(d[2]), 4)]


def clamp(v, lo_hi):
    return min(max(float(v), float(lo_hi[0])), float(lo_hi[1]))


# ------------------------------------------------------------------ build
def build(map_key: str, base: dict, spec: dict, report: dict | None) -> tuple[dict, dict]:
    L = spec["layout"]
    pre = L.get("idPrefix", "cp-")
    shadow = bool(L.get("castShadow", False))
    overlay = {"schema": OVERLAY_SCHEMA, "map": map_key, "variant": L["variant"], "boardId": base["boardId"],
               "props": {"remove": [p["id"] for p in base["props"]]}}
    removed = set(overlay["props"]["remove"])
    info = {"removedProps": len(removed),
            "fxDroppedWithAnchor": sorted(f["id"] for f in base.get("fx", []) if f.get("anchor") in removed)}
    details = pp.detail_positions(spec, C.concept_cam(), "relief") if spec.get("details") else []
    by_id = {d["id"]: d for d in details}
    add_props, add_fx = [], []
    placed = {}
    if details and any(d["kind"] != "paint-lantern" for d in details):
        if report is None:
            raise RuntimeError("the asset build report is needed for the detail meshes (cp_proxies.py build)")
        lant =export_of(report, Path(L["lantern"]["mesh"]).name)
        head_h = float(lant["boundsUeLocalUU"]["size"][2])
        glow = np.array(lant["glowOffsetUU"], float)
        # P7c: the overlay places the dark-iron copy (SM_EnvCP_Cannon, ue_import_concept_paste.py), measured on the kit mesh
        cannon = report["kitMeasurements"][L["cannon"].get("measureMesh", Path(L["cannon"]["mesh"]).name)]
        can_len = float(cannon["boundsUU"]["max"][0]) - float(cannon["boundsUU"]["min"][0])
        ban = export_of(report, Path(L["banner"]["mesh"]).name)
        cloth_w = float(ban["clothWidthUU"])
        bar_top = float(ban["crossbarTopUU"])
    if details:
        for d in details:
            P = np.array(d["world"], float)
            pid = pre + d["id"]
            if d["kind"] == "paint-lantern":
                # VS-5 EN-07: painted, no mesh: only the world point (lights / anim slots reference)
                placed[d["id"]] = {"kind": "paint-lantern", "glowWorld": [r2(v) for v in P], "c0Px": d["px"]}
                continue
            if d["kind"] == "lantern":
                yaw = float(L["lantern"]["yawDeg"])
                s = clamp(d["sizeUU"][1] * float(L["lantern"].get("sizeMul", 1.0)) / head_h, L["lantern"]["scaleRange"])
                loc = P - rot_yaw(glow * s, yaw)
                add_props.append({"id": pid, "mesh": L["lantern"]["mesh"], "loc": [r2(v) for v in loc], "yawDeg": yaw,
                                  "scale": round(s, 3), "castShadow": shadow})
                fl = L["lantern"]["flame"]
                fid = "flame-" + pid
                add_fx.append({"id": fid, "system": fl["system"], "anchor": pid, "loc": [r2(v) for v in glow * s],
                               "yawDeg": 0.0, "scale": round(s, 3), "seed": seed_of(fid), "warmupS": fl["warmupS"]})
                placed[d["id"]] = {"kind": "lantern", "scale": round(s, 3), "glowWorld": [r2(v) for v in P]}
            elif d["kind"] == "cannon":
                yaw = float(L["cannon"]["yawDeg"])
                s = clamp(d["sizeUU"][0] * float(L["cannon"].get("sizeMul", 1.0)) / can_len, L["cannon"]["scaleRange"])
                axis = np.array([0.0, float(cannon["barrelAxisYUU"]), float(cannon["barrelAxisZUU"])])
                loc = P - rot_yaw(axis * s, yaw)
                add_props.append({"id": pid, "mesh": L["cannon"]["mesh"], "loc": [r2(v) for v in loc], "yawDeg": yaw,
                                  "scale": round(s, 3), "castShadow": shadow})
                placed[d["id"]] = {"kind": "cannon", "scale": round(s, 3), "barrelWorld": [r2(v) for v in P]}
            elif d["kind"] == "banner":
                yaw = round(ship_yaw(spec), 2)
                s = clamp(d["sizeUU"][0] / cloth_w, L["banner"]["scaleRange"])
                # P7c "towardC0UU": the whole cloth moves along the C0 ray of its top attachment towards the camera (same
                # C0 pixel), the scale x (D - d) / D keeps its C0 size: a rigid shift off the ship's hull plane of the
                # depth sheet by d x (ray . hull normal), so the sheet no longer clips it (P7b review: 115 of ~360 px)
                tow = float(L["banner"].get("towardC0UU", 0.0))
                if tow > 0.0:
                    ray = P - C.concept_cam().pos
                    D = float(np.linalg.norm(ray))
                    P = P - ray / D * tow
                    s = s * (D - tow) / D
                # P7c: the sheared cloth (hangLocal) puts the rail off the pivot axis
                rail = np.array([float(ban.get("crossbarXUU", 0.0)), float(ban.get("crossbarYUU", 0.0)), bar_top])
                loc = P - rot_yaw(rail * s, yaw)
                add_props.append({"id": pid, "mesh": L["banner"]["mesh"], "loc": [r2(v) for v in loc], "yawDeg": yaw,
                                  "scale": round(s, 3), "castShadow": shadow})
                placed[d["id"]] = {"kind": "banner", "scale": round(s, 3), "topWorld": [r2(v) for v in P],
                                   "clothLengthUU": r2(float(ban["clothLengthUU"]) * s),
                                   "towardC0UU": float(L["banner"].get("towardC0UU", 0.0))}
            elif d["kind"] in ("campfire", "brazier"):
                F = L["fire"]
                k = F[d["kind"]]
                fid = pid  # fire-fort / fire-brazier (fx ids are their own namespace)
                # optional "towardC0UU": moves the fx origin along its C0 ray towards the camera (same C0 pixel), e.g. in
                # front of a host flat of the sheet (0 / absent = the design point; P7 tune tried 30 on the brazier: no
                # effect on the cooked client's missing second campfire, which P6 shows too - reverted)
                Q = np.array([P[0], P[1], P[2] + k["dz"]])
                ray = Q - C.concept_cam().pos
                Q = Q - ray / np.linalg.norm(ray) * float(k.get("towardC0UU", 0.0))
                add_fx.append({"id": fid, "system": F["system"], "loc": [r2(Q[0]), r2(Q[1]), r2(Q[2])],
                               "yawDeg": 0.0, "scale": k["scale"], "seed": seed_of(fid), "warmupS": F["warmupS"]})
                placed[d["id"]] = {"kind": d["kind"], "fxWorld": [r2(P[0]), r2(P[1]), r2(P[2] + k["dz"])]}
            else:
                raise ValueError(f"unknown detail kind {d['kind']}")
    overlay["props"]["add"] = add_props
    fx_ops = {}
    ff = L.get("fireflies")
    base_fx = {f["id"]: f for f in base.get("fx", [])}
    if ff:
        fx_ops["remove"] = [i for i in ff["remove"] if i in base_fx]
        fx_ops["replace"] = [{"id": i, "loc": [r2(v) for v in loc]} for i, loc in ff["replace"].items() if i in base_fx]
    if L.get("fxRemoveBase"):
        # VS-5 EN-07: every base fx goes (those anchored on a removed prop are dropped with it by MergeOverlay)
        fx_ops["remove"] = [f["id"] for f in base.get("fx", []) if f.get("anchor") not in removed]
        info["fxRemoved"] = list(fx_ops["remove"])
    for fl in L.get("fx", []):
        # VS-5 EN-09 / EN-11: the concept's own environment fx (petals under the painted crowns, fireflies at the
        # painted bushes): the C0 ray through the painted pixel hits the plane z = planeZ (the heightZones crown
        # plane / the ground), +dz (the height of the spawn box) and optionally towardC0UU along the same C0 ray
        # towards the camera (in front of the relief sheet, the same C0 pixel); no anchor, a fixed seed
        Q = pp.ray_z(C.concept_cam(), np.array(float(fl["c0Px"][0])), np.array(float(fl["c0Px"][1])),
                     float(fl["planeZ"]))[0]
        Q = Q + np.array([0.0, 0.0, float(fl.get("dz", 0.0))])
        tow = float(fl.get("towardC0UU", 0.0))
        if tow > 0.0:
            ray = Q - C.concept_cam().pos
            Q = Q - ray / np.linalg.norm(ray) * tow
        entry = {"id": fl["id"], "system": fl["system"], "loc": [r2(Q[0]), r2(Q[1]), r2(Q[2])], "yawDeg": 0.0,
                 "scale": float(fl.get("scale", 1.0)), "seed": seed_of(fl["id"]), "warmupS": float(fl["warmupS"])}
        if fl.get("reducedMotion"):
            entry["reducedMotion"] = fl["reducedMotion"]
        if fl.get("user"):
            entry["user"] = fl["user"]
        add_fx.append(entry)
        info.setdefault("conceptFx", []).append(fl["id"])
    if add_fx:
        fx_ops["add"] = add_fx
    if fx_ops:
        overlay["fx"] = fx_ops
    cp = {"spec": f"tools/art/concept_paste/{map_key}.paste.json",
          "manifest": f"tools/art/concept_paste/manifest.{map_key}.json",
          "assets": "art/pipeline-candidates/ASSET-ENV-CONCEPT-PASTE-001/20261001-p7/reports/build-report.json",
          "hideByProfile": ["SM_TableBase_T2 + T2b lip", "ground strips + splat", "SM_Env_S_SeaRing",
                            "ground.waterfalls (sheet / foam / lip / spill)", "profile backdrop moon", "profile fog"]
          if map_key == "sarpedon" else ["SM_TableBase_T2 + T2b lip", "ground strips + splat", "profile backdrop"]}
    if L.get("lights"):
        # the profile block (S08ArtBoardProfiles.json conceptPaste.lights + flicker, track B) owns the concept-mode
        # lights; this list is the reference for its positions (the true fire / lantern points of the details)
        ref = []
        for lt in L["lights"]:
            P = np.array(placed[lt["on"]].get("glowWorld") or placed[lt["on"]].get("fxWorld"), float)
            ref.append({"id": lt["id"], "loc": [r2(P[0]), r2(P[1]), r2(P[2] + lt["dz"])]})
        cp["lights"] = {"mode": "profile", "reference": ref,
                        "note": "informational: the profile block conceptPaste carries the lights (hide 'layoutLights'); "
                                "MergeOverlay refuses a top-level 'lights' - the base light budget stays protected"}
    else:
        cp["lights"] = {"mode": "base", "note": "the base layout's lights stay"}
    paint = [{"id": k, "c0Px": v["c0Px"], "world": v["glowWorld"]} for k, v in placed.items() if v["kind"] == "paint-lantern"]
    if paint:
        cp["paintLanterns"] = paint
    overlay["conceptPaste"] = cp
    overlay["notes"] = (f"ENV-MAPS P7 concept mode (ENV-U15), variant '{L['variant']}', written by "
                        f"tools/art/concept_paste/cp_layout.py from {map_key}.paste.json + the P7 asset build report. "
                        "Status: предложено (CREATE stage, nothing rendered in UE yet).")
    info.update(addedProps=len(add_props), addedFx=len(add_fx), placed=placed)
    return overlay, info


# ------------------------------------------------------------------ validation (Python twin of MergeOverlay + checks)
def merge(base: dict, overlay: dict) -> dict:
    out = copy.deepcopy(base)
    for fixed in ("lights", "ground", "tray", "apron"):
        if fixed in overlay:
            raise ValueError(f"overlay cannot change '{fixed}'")
    removed_props: list[str] = []
    for section, fields in (("props", ("mesh", "loc", "yawDeg", "scale", "castShadow")),
                            ("fx", ("system", "anchor", "loc", "yawDeg", "scale", "seed", "warmupS", "enabled", "user",
                                    "reducedMotion"))):
        ops = overlay.get(section, {})
        items = out.get(section, [])
        dropped = []
        if section == "fx" and removed_props:
            dropped = [f["id"] for f in items if f.get("anchor") in removed_props]
            items = [f for f in items if f.get("anchor") not in removed_props]
        for rid in ops.get("remove", []):
            idx = [i for i, x in enumerate(items) if x["id"] == rid]
            if not idx:
                if rid in dropped:
                    continue
                raise ValueError(f"{section}.remove: {rid} not in the base")
            items.pop(idx[0])
            if section == "props":
                removed_props.append(rid)
        for rep in ops.get("replace", []):
            idx = [i for i, x in enumerate(items) if x["id"] == rep["id"]]
            if not idx:
                raise ValueError(f"{section}.replace: {rep['id']} not in the base")
            for k, v in rep.items():
                if k != "id":
                    if k not in fields:
                        raise ValueError(f"{section}.replace {rep['id']}: field {k} cannot be replaced")
                    items[idx[0]][k] = v
        for add in ops.get("add", []):
            if any(x["id"] == add["id"] for x in items):
                raise ValueError(f"{section}.add: {add['id']} exists")
            items.append(add)
        out[section] = items
    return out


def validate(map_key: str, base: dict, overlay: dict) -> list[str]:
    err = []
    try:
        merged = merge(base, overlay)
    except ValueError as exc:
        return [f"merge: {exc}"]
    ids = [p["id"] for p in merged["props"]]
    if len(ids) != len(set(ids)):
        err.append("duplicate prop ids")
    fx_ids = [f["id"] for f in merged.get("fx", [])]
    if len(fx_ids) != len(set(fx_ids)):
        err.append("duplicate fx ids")
    for p in merged["props"]:
        if not p["mesh"].startswith(KIT_ROOT):
            err.append(f"prop {p['id']}: mesh outside {KIT_ROOT}")
        if any(n in p["mesh"] for n in NOAI_ROOTS) or "/UserFab/" in p["mesh"]:
            err.append(f"prop {p['id']}: NoAI / user mesh in the concept overlay")
        if not (0 < float(p.get("scale", 1)) <= 20):
            err.append(f"prop {p['id']}: scale out of (0, 20]")
        x, y = p["loc"][:2]
        if abs(x) < C.MAP_HX and abs(y) < C.MAP_HY:
            err.append(f"prop {p['id']}: pivot on the painted map")
    for f in merged.get("fx", []):
        if not f["system"].startswith(KIT_ROOT):
            err.append(f"fx {f['id']}: system outside {KIT_ROOT}")
        if f.get("anchor") and f["anchor"] not in ids:
            err.append(f"fx {f['id']}: anchor {f['anchor']} not a prop")
        if not (0 <= float(f.get("warmupS", 2.0)) <= 10):
            err.append(f"fx {f['id']}: warmupS out of range")
        if not f.get("anchor"):
            x, y = f["loc"][:2]
            if abs(x) < C.MAP_HX and abs(y) < C.MAP_HY:
                err.append(f"fx {f['id']}: pivot on the painted map")
    # VS-5 EN-09 / EN-11 (ВР-EN.6): the concept's own environment fx keep their spawn sphere off the frame rectangle
    # and away from the painted lantern glass, and are not spawned with reduced motion (02 §10.1)
    spec_fx = {fl["id"]: fl for fl in pp.load_spec(map_key).get("layout", {}).get("fx", [])} if map_key == "marmoreal" else {}
    for f in overlay.get("fx", {}).get("add", []):
        fl = spec_fx.get(f["id"])
        if fl is None:
            continue
        r = float(fl.get("spawnRadiusUU", 0.0)) + float(fl.get("wanderUU", 0.0))
        x, y = f["loc"][:2]
        if abs(x) - r <= C.FRAME_HX and abs(y) - r <= C.FRAME_HY:
            err.append(f"fx {f['id']}: spawn sphere (r {r:g}) reaches the frame rectangle")
        if f.get("reducedMotion") != "off":
            err.append(f"fx {f['id']}: concept environment fx must be reducedMotion off")
        min_l = float(fl.get("minLanternUU", 0.0))
        for pl in overlay.get("conceptPaste", {}).get("paintLanterns", []):
            d = math.dist(f["loc"], pl["world"]) - float(fl.get("spawnRadiusUU", 0.0))
            if min_l and d < min_l:
                err.append(f"fx {f['id']}: {d:.1f} uu from the painted lantern {pl['id']} < {min_l:g}")
    if map_key == "sarpedon" and BUILD_REPORT.is_file():
        rep = load(BUILD_REPORT)
        ban = next((e for e in rep["exports"] if e["name"] == "SM_EnvCP_BannerCloth"), None)
        want = banner_hang_local(pp.load_spec(map_key))
        got = (ban or {}).get("hangLocal")
        if got is None or max(abs(a - b) for a, b in zip(got, want)) > 2e-3:
            err.append(f"SM_EnvCP_BannerCloth hangLocal {got} != the C0 screen-down {want} (blender_cp_assets.py --only banner)")
    lights = overlay.get("conceptPaste", {}).get("lights", {})
    ref = lights.get("reference", [])
    n_lights = len(ref) if lights.get("mode") == "profile" else len(base.get("lights", []))
    if n_lights + PROFILE_POINTS > MAX_POINT_LIGHTS:
        err.append(f"light budget: {n_lights} layout + {PROFILE_POINTS} profile > {MAX_POINT_LIGHTS}")
    for lt in ref:
        x, y = lt["loc"][:2]
        if abs(x) < C.MAP_HX and abs(y) < C.MAP_HY:
            err.append(f"light {lt['id']}: on the painted map")
    return err


def text_of(overlay: dict) -> str:
    return json.dumps(overlay, indent=2, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    ap.add_argument("--maps", default="sarpedon,marmoreal")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--layouts", type=Path, default=LAYOUTS)
    ap.add_argument("--report", type=Path, default=BUILD_REPORT)
    a = ap.parse_args(argv)
    report = load(a.report) if a.report.is_file() else None
    ok = True
    for key in [m.strip() for m in a.maps.split(",") if m.strip()]:
        spec = pp.load_spec(key)
        base = load(a.layouts / f"{key}.layout.json")
        overlay, info = build(key, base, spec, report)
        errs = validate(key, base, overlay)
        path = a.layouts / f"{key}.{spec['layout']['variant']}.layout.json"
        text = text_of(overlay)
        if a.check:
            same = path.is_file() and path.read_text(encoding="utf-8") == text
            if not same:
                errs.append(f"{path.name} differs from a fresh generation (run cp_layout.py)")
        else:
            path.write_text(text, encoding="utf-8", newline="\n")
        ok = ok and not errs
        print(f"CP-LAYOUT {key} {'ok' if not errs else 'FAILED'} props-={info['removedProps']} "
              f"props+={info['addedProps']} fx+={info['addedFx']} -> {path.name}" + ("; " + "; ".join(errs) if errs else ""))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
