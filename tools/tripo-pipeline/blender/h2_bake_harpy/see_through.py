"""See-through gate of a one-sided figure in the game camera (headless Blender only).

    blender -b --factory-startup --python see_through.py -- <profile.json> <run_dir> [--blend <file>] [--out <json>]
                                                            [--frames <dir>] [--no-gate]

M_UM_Figure is TwoSided=false (tripo_pipeline um-master route), so a back face that is the first hit of a camera ray
is culled in UE and the ray continues behind it. Where the figure has an open shell (a cut Tripo part, a dropped
part), the background shows through the figure. This stage measures exactly that, per game-camera frame:

  covered_two_sided   = pixels where the figure (both face sides) covers the background
  covered_one_sided   = the same with back-face culling (what UE draws with TwoSided=false)
  see_through_px      = covered_two_sided AND NOT covered_one_sided

Workbench, flat single colour, no anti-aliasing, transparent film (alpha = coverage), 1920x1080, horizontal FOV 35,
pitch -55 (the K1/K2 game camera of review_h2.py), target (0, 0, 0.12), figure alone at the origin (body + base of
<run>/work/h2-candidate.blend in the rest pose). Azimuth 0 = in front of the figure (-Y), 180 = behind (+Y).

Two gates (profile review.see_through, proposals):
  gate_strict  the verifier's gate: see_through_px <= gate_max_px (0) for azimuths gate_azimuth_range_deg (120..240)
               at every distance - reported (pass_strict), does not stop the run;
  gate         no opening: no 8-connected see-through component of hole_min_px (4) pixels or more at any azimuth and
               distance (gate_max_holes 0) - an opening such as the harpy-h2-bake/1 neck gap (components of 44 and
               69 px at azimuth 180 / 4.8 m) fails it; isolated 1-3 px pinholes (sub-millimetre cracks) are counted and
               reported but pass. The stage raises (run_all.sh stops) when this gate fails, unless --no-gate.
Frames with see-through pixels are written as PNG with the pixels marked (red) for the report. Output:
<run>/reports/see-through.json.
"""

import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402

DEFAULTS = {"azimuths_deg": list(range(0, 360, 20)), "distances_m": [4.8, 7.5], "gate_strict_distances_m": None,
            "gate_azimuth_range_deg": [120, 240],
            "gate_max_px": 0, "hole_min_px": 4, "gate_max_holes": 0, "resolution": [1920, 1080], "fov_h_deg": 35.0,
            "pitch_deg": -55.0, "target_m": [0.0, 0.0, 0.12]}


def components(mask):
    """Sizes of the 8-connected components of a sparse boolean image (largest first)."""
    ys, xs = np.nonzero(mask)
    todo = set(zip(ys.tolist(), xs.tolist()))
    sizes = []
    while todo:
        stack = [todo.pop()]
        n = 0
        while stack:
            y, x = stack.pop()
            n += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    q = (y + dy, x + dx)
                    if q in todo:
                        todo.remove(q)
                        stack.append(q)
        sizes.append(n)
    return sorted(sizes, reverse=True)


def game_dir(azimuth_deg, pitch_deg):
    el = math.radians(-pitch_deg)
    az = math.radians(azimuth_deg)
    return Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))


def setup(scene, cfg):
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "FLAT"
    sh.color_type = "SINGLE"
    sh.single_color = (0.2, 0.2, 0.2)
    sh.show_cavity = False
    sh.show_shadows = False
    sh.show_object_outline = False
    sh.show_specular_highlight = False
    scene.display.render_aa = "OFF"
    scene.render.film_transparent = True
    scene.render.resolution_x, scene.render.resolution_y = cfg["resolution"]
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    cam = bpy.data.objects.new("h2_seethrough_cam", bpy.data.cameras.new("h2_seethrough_cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.type = "PERSP"
    cam.data.sensor_fit = "HORIZONTAL"
    cam.data.angle = math.radians(cfg["fov_h_deg"])
    cam.data.clip_start = 0.01
    cam.data.clip_end = 100.0
    return cam


def coverage(scene, path, cull):
    scene.display.shading.show_backface_culling = cull
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    im = bpy.data.images.load(str(path), check_existing=False)
    w, h = im.size
    px = np.empty(w * h * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    a = px.reshape(h, w, 4)[::-1, :, 3]  # top row first
    return a > 0.5


def measure(scene, cam, cfg, tmp_dir, frames_dir=None, tag=""):
    tmp_dir = Path(tmp_dir)
    tmp_dir.mkdir(parents=True, exist_ok=True)
    target = Vector(cfg["target_m"])
    lo, hi = cfg["gate_azimuth_range_deg"]
    rows = []
    for dist in cfg["distances_m"]:
        for az in cfg["azimuths_deg"]:
            d = game_dir(az, cfg["pitch_deg"])
            cam.location = target + d * float(dist)
            cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
            two = coverage(scene, tmp_dir / "two.png", False)
            one = coverage(scene, tmp_dir / "one.png", True)
            see = two & ~one
            n = int(see.sum())
            comp = components(see)
            row = {"azimuth_deg": az, "distance_m": dist, "covered_two_sided_px": int(two.sum()),
                   "covered_one_sided_px": int(one.sum()), "see_through_px": n,
                   "components_px": comp[:8], "holes": int(sum(1 for c in comp if c >= cfg["hole_min_px"])),
                   "gated": bool(lo <= az % 360 <= hi)}
            if n:
                ys, xs = np.nonzero(see)
                row["bbox_px"] = [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
                if frames_dir is not None:
                    Path(frames_dir).mkdir(parents=True, exist_ok=True)
                    img = np.where(two, 0.35, 1.0)[..., None].repeat(3, 2)
                    img[see] = (1.0, 0.0, 0.0)
                    name = "seethrough_%saz%03d_d%.1f.png" % (tag, az % 360, dist)
                    save_rgb(img, Path(frames_dir) / name)
                    row["frame"] = name
            rows.append(row)
            print("see-through", tag, dist, az, n, flush=True)
    for f in ("two.png", "one.png"):
        p = tmp_dir / f
        if p.exists():
            p.unlink()
    sd = cfg.get("gate_strict_distances_m") or cfg["distances_m"]
    for r in rows:
        r["gated"] = bool(r["gated"] and any(abs(r["distance_m"] - x) < 1e-9 for x in sd))
    gated = [r for r in rows if r["gated"]]
    return {"frames": rows,
            # the verifier's strict gate: no see-through pixel at all behind the figure (reported, see pass_strict)
            "gate_strict": {"azimuth_range_deg": [lo, hi], "distances_m": sd, "max_px": cfg["gate_max_px"],
                            "worst_px": max((r["see_through_px"] for r in gated), default=0),
                            "pass": all(r["see_through_px"] <= cfg["gate_max_px"] for r in gated)},
            # the stage gate: no opening = no 8-connected see-through component of hole_min_px or more, all azimuths
            "gate": {"azimuth_range_deg": [0, 360], "distances_m": cfg["distances_m"], "hole_min_px": cfg["hole_min_px"],
                     "max_holes": cfg["gate_max_holes"], "holes": int(sum(r["holes"] for r in rows)),
                     "largest_component_px": max((r["components_px"][0] for r in rows if r["components_px"]), default=0),
                     "pass": sum(r["holes"] for r in rows) <= cfg["gate_max_holes"]},
            "strict_all_distances": {"azimuth_range_deg": [lo, hi], "distances_m": cfg["distances_m"],
                                     "worst_px": max((r["see_through_px"] for r in rows if lo <= r["azimuth_deg"] % 360 <= hi),
                                                     default=0)},
            "by_distance_total_px": {str(d): int(sum(r["see_through_px"] for r in rows if r["distance_m"] == d))
                                     for d in cfg["distances_m"]},
            "all_azimuths_worst_px": max((r["see_through_px"] for r in rows), default=0),
            "all_azimuths_total_px": int(sum(r["see_through_px"] for r in rows))}


def save_rgb(img, path):
    h, w, _ = img.shape
    im = bpy.data.images.new("h2_seethrough_out", w, h, alpha=False)
    rgba = np.concatenate([img[::-1], np.ones((h, w, 1))], axis=2).astype(np.float32)
    im.pixels.foreach_set(rgba.reshape(-1))
    im.filepath_raw = str(path)
    im.file_format = "PNG"
    im.save()
    bpy.data.images.remove(im)


def main():
    C.require_background("see_through.py")
    a = C.script_args()
    profile_path, run = Path(a[0]).resolve(), Path(a[1]).resolve()
    P = C.load_profile(profile_path)
    blend = Path(a[a.index("--blend") + 1]).resolve() if "--blend" in a else run / "work" / "h2-candidate.blend"
    out = Path(a[a.index("--out") + 1]).resolve() if "--out" in a else run / "reports" / "see-through.json"
    frames_dir = Path(a[a.index("--frames") + 1]).resolve() if "--frames" in a else run / "preview" / "see-through"
    key = a[a.index("--config-key") + 1] if "--config-key" in a else "see_through"
    cfg = dict(DEFAULTS)
    cfg.update({k: v for k, v in P.get("review", {}).get(key, {}).items() if k in DEFAULTS})
    bpy.ops.wm.open_mainfile(filepath=str(blend))
    scene = bpy.context.scene
    N_ = P["names"]
    keep = {N_["body_object"], N_["base_object"]}
    for o in list(scene.objects):
        if o.type == "MESH" and o.name not in keep:
            o.hide_render = True
        elif o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o)
        elif o.type == "ARMATURE":
            o.hide_render = True
    cam = setup(scene, cfg)
    res = measure(scene, cam, cfg, run / "work" / "see-through-tmp", frames_dir)
    blend_label = C.rel(blend)
    if ":" in blend_label or blend_label.startswith("/"):  # outside the repository (a local copy of an older run)
        blend_label = "external:" + "/".join(blend.parts[-3:])
    res.update({"schema": "unmatched.h2-bake.see-through/1", "config_key": key, "blend": blend_label,
                "blend_sha256": C.sha256(blend),
                "label": "blender Workbench mask (flat, no AA), not an UE frame",
                "camera": {k: cfg[k] for k in ("resolution", "fov_h_deg", "pitch_deg", "target_m")},
                "method": "see_through_px = covered with both face sides AND NOT covered with back faces culled "
                          "(M_UM_Figure TwoSided=false)"})
    C.write_json(out, res)
    print("see-through gate", res["gate"], "strict", res["gate_strict"], flush=True)
    if not res["gate"]["pass"] and "--no-gate" not in a:
        raise RuntimeError("see-through gate failed: %s" % res["gate"])
    print(C.STAGE_MARKER, "see-through", res["gate"]["holes"], res["gate_strict"]["worst_px"], flush=True)


if __name__ == "__main__":
    main()
