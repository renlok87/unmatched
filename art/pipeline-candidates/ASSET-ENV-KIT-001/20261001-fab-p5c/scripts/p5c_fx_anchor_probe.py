#!/usr/bin/env python3
"""ENV-MAPS P5c track V: where the flames go - the glowing texels of our own kit meshes, measured headless in Blender.

  python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-fab-p5c/scripts/p5c_fx_anchor_probe.py [--blender EXE]

Plain Python re-launches itself inside Blender (-b --factory-startup -t 4, BELOW_NORMAL priority, no window); inside
Blender it imports the processed kit FBX (UM_FBX_v1 export of the env-kit runs, scale 1 = uu after x100), samples the
base colour texture (T_Env_<Name>_BC.png) at every face's UV centroid and keeps the faces whose texel matches the glow
rule of the mesh (lantern glass = the pale amber panes of env-prop-look.json, hue 30..55 deg, V >= 0.68; campfire =
the orange embers / flame hue 5..45 deg, S >= 0.55, V >= 0.55). Result: the area-weighted centroid and the bounds of
those faces in the UE mesh frame (pivot = base centre, X = front, Y = width, Z = up; UE Y = -Blender Y, the FBX
handedness flip), written to reports/p5c-fx-anchors.json. The fx layout generator (p5c_layout_fx.py) turns them into
anchor offsets (x prop scale). Only our own Tripo kit assets are read (no Fab pack, no NoAI asset); nothing is
rendered.
"""
from __future__ import annotations

import colorsys
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE.parent
REPO = HERE.parents[4]
OUT = RUN / "reports" / "p5c-fx-anchors.json"
KIT = REPO / "art/pipeline-candidates/ASSET-ENV-KIT-001"
DEFAULT_BLENDER = os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe")
NO_WINDOW = (0x08000000 | 0x00004000) if os.name == "nt" else 0  # CREATE_NO_WINDOW | BELOW_NORMAL_PRIORITY_CLASS

# mesh -> (run folder, glow rule: hue range deg, min S, min V)
PROBES = {
    "SM_Env_LanternPost": ("20261001-tripo-h31-p5", {"hue": (30.0, 55.0), "s": 0.15, "v": 0.68}),
    "SM_Env_LanternPlinth": ("20260930-tripo-h31", {"hue": (30.0, 55.0), "s": 0.15, "v": 0.68}),
    "SM_Env_Campfire": ("20260930-tripo-h31", {"hue": (5.0, 45.0), "s": 0.55, "v": 0.55}),
}


def rel(p: Path) -> str:
    return Path(p).resolve().relative_to(REPO).as_posix()


# ------------------------------------------------------------------------------------------------ inside Blender
def probe_in_blender() -> dict:
    import bpy  # type: ignore
    import numpy as np  # type: ignore

    out: dict = {"schema": "unmatched.env-fx-anchors/1", "tool": rel(Path(__file__)), "status": "measured",
                 "frame": "UE mesh frame (uu): X front, Y width (UE Y = -Blender Y), Z up, pivot = base centre",
                 "blender": bpy.app.version_string, "meshes": {}}
    for name, (run, rule) in PROBES.items():
        fbx = KIT / run / "export" / f"{name}.fbx"
        tex = KIT / run / "export" / f"T_Env_{name[len('SM_Env_'):]}_BC.png"
        entry: dict = {"fbx": rel(fbx), "bc": rel(tex), "rule": rule}
        out["meshes"][name] = entry
        if not fbx.is_file() or not tex.is_file():
            entry["error"] = "fbx or BC texture missing"
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.fbx(filepath=str(fbx))
        objs = [o for o in bpy.context.scene.objects if o.type == "MESH"]
        if len(objs) != 1:
            entry["error"] = f"{len(objs)} mesh objects"
            continue
        obj = objs[0]
        img = bpy.data.images.load(str(tex))
        w, h = img.size
        px = np.array(img.pixels[:], dtype=np.float32).reshape(h, w, img.channels)
        mesh = obj.data
        mw = obj.matrix_world
        uv = mesh.uv_layers.active.data
        lo = [1e9, 1e9, 1e9]
        hi = [-1e9, -1e9, -1e9]
        glow_lo = [1e9, 1e9, 1e9]
        glow_hi = [-1e9, -1e9, -1e9]
        acc = [0.0, 0.0, 0.0]
        area_all = area_glow = 0.0
        faces = 0
        for v in mesh.vertices:
            p = mw @ v.co
            q = (p.x * 100.0, -p.y * 100.0, p.z * 100.0)
            for i in range(3):
                lo[i] = min(lo[i], q[i])
                hi[i] = max(hi[i], q[i])
        for poly in mesh.polygons:
            a = poly.area
            area_all += a
            us = [uv[li].uv for li in poly.loop_indices]
            u = sum(t[0] for t in us) / len(us)
            vv = sum(t[1] for t in us) / len(us)
            x = min(w - 1, max(0, int((u % 1.0) * w)))
            y = min(h - 1, max(0, int((vv % 1.0) * h)))  # Blender image rows start at the bottom = UV v 0
            r, g, b = (float(c) for c in px[y, x, :3])
            hh, ss, vv2 = colorsys.rgb_to_hsv(r, g, b)
            hue = hh * 360.0
            if not (rule["hue"][0] <= hue <= rule["hue"][1] and ss >= rule["s"] and vv2 >= rule["v"]):
                continue
            c = mw @ poly.center
            q = (c.x * 100.0, -c.y * 100.0, c.z * 100.0)
            for i in range(3):
                acc[i] += q[i] * a
                glow_lo[i] = min(glow_lo[i], q[i])
                glow_hi[i] = max(glow_hi[i], q[i])
            area_glow += a
            faces += 1
        entry["meshBoundsUU"] = {"min": [round(t, 2) for t in lo], "max": [round(t, 2) for t in hi]}
        entry["glowFaces"] = faces
        entry["glowAreaFraction"] = round(area_glow / area_all, 5) if area_all else 0.0
        if faces:
            entry["glowCentroidUU"] = [round(t / area_glow, 2) for t in acc]
            entry["glowBoundsUU"] = {"min": [round(t, 2) for t in glow_lo], "max": [round(t, 2) for t in glow_hi]}
        else:
            entry["error"] = "no face matched the glow rule"
    return out


# ------------------------------------------------------------------------------------------------ plain Python
def main(argv: list[str]) -> int:
    if "bpy" in sys.modules or _in_blender():
        args = argv[argv.index("--") + 1:] if "--" in argv else []
        out = Path(args[args.index("--out") + 1]) if "--out" in args else OUT
        res = probe_in_blender()
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes((json.dumps(res, indent=1, ensure_ascii=False) + "\n").encode("utf-8"))
        print("P5C-FX-ANCHORS " + json.dumps({k: v.get("glowCentroidUU") for k, v in res["meshes"].items()}))
        return 0
    blender = DEFAULT_BLENDER
    if "--blender" in argv:
        blender = argv[argv.index("--blender") + 1]
    cmd = [blender, "-b", "--factory-startup", "-t", "4", "--python-exit-code", "1", "--python", str(Path(__file__)),
           "--", "--out", str(OUT)]
    res = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, errors="replace", creationflags=NO_WINDOW)
    lines = [ln for ln in res.stdout.splitlines() if ln.startswith("P5C-FX-ANCHORS")]
    print("\n".join(lines) if lines else res.stdout[-2000:] + res.stderr[-2000:])
    return res.returncode


def _in_blender() -> bool:
    try:
        import bpy  # type: ignore  # noqa: F401
        return True
    except ImportError:
        return False


if __name__ == "__main__":
    sys.exit(main(sys.argv))
