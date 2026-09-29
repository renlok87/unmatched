"""M_UM_Figure v2 in the LIVE UnrealEditor (MCP 127.0.0.1:8123 + editor console, tools/tripo-pipeline/review/ue_live.py).

    python tools/art/material_library/build_ue_inputs.py              # host: arrays, LUT, test textures (first)
    python tools/art/material_library/ue_v2.py import  --report <dir>  # textures -> /Game/UM/Materials/v2/Textures
    python tools/art/material_library/ue_v2.py master  --report <dir>  # M_UM_Figure_v2 + MI template + test MIs, stats
    python tools/art/material_library/ue_v2.py scene   --report <dir>  # class spheres on the Cobble light, frames
    python tools/art/material_library/ue_v2.py v1check --report <dir> [--v1-baseline <report>]  # v1 unchanged
    python tools/art/material_library/ue_v2.py stats   --report <dir>  # statistics v1 vs v2 (read-only)

Rules (task LD-master, 2026-09-29): only /Game/UM/Materials/v2/ is written; the v1 masters (/Game/UM/Materials/M_UM_*)
and their textures are read-only references; the editor is shared (never restarted, other packages never saved).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "tripo-pipeline" / "review"))
from ue_live import Ue  # noqa: E402

INPUTS = REPO / "art" / "material-library" / "v2-ue"
ROOT = "/Game/UM/Materials/v2"
TEX = ROOT + "/Textures"
CONTENT = REPO / "unreal" / "Unmatched" / "Content"
V1_FILES = ["UM/Materials/M_UM_BaseMarker.uasset", "UM/Materials/M_UM_Figure.uasset",
            "UM/Materials/M_UM_GameLayer.uasset", "UM/Materials/Textures/T_UM_Default_BC.uasset",
            "UM/Materials/Textures/T_UM_Default_N.uasset", "UM/Materials/Textures/T_UM_Default_ORM.uasset",
            "UM/Materials/Textures/T_UM_Mask_Black.uasset", "UM/Materials/Textures/T_UM_Mask_White.uasset"]

POINT_NO_MIPS = {"srgb": False, "filter": "TF_NEAREST", "mip_gen_settings": "TMGS_NO_MIPMAPS", "never_stream": True,
                 "lod_group": "TEXTUREGROUP_WORLD"}


def texture_specs() -> list:
    arr = INPUTS / "arrays"
    specs = [
        {"file": arr / "T_UM_DetailN_Array.dds", "asset": TEX + "/T_UM_DetailN_Array", "class": "Texture2DArray",
         "settings": {"compression_settings": "TC_NORMALMAP", "srgb": False, "lod_group": "TEXTUREGROUP_WORLD_NORMAL_MAP",
                      "mip_gen_settings": "TMGS_FROM_TEXTURE_GROUP", "address_x": "TA_WRAP", "address_y": "TA_WRAP"}},
        {"file": arr / "T_UM_DetailRMH_Array.dds", "asset": TEX + "/T_UM_DetailRMH_Array", "class": "Texture2DArray",
         "settings": {"compression_settings": "TC_BC7", "srgb": False, "lod_group": "TEXTUREGROUP_WORLD",
                      "mip_gen_settings": "TMGS_FROM_TEXTURE_GROUP", "address_x": "TA_WRAP", "address_y": "TA_WRAP"}},
        {"file": INPUTS / "lut" / "T_UM_MatLUT_Global.dds", "asset": TEX + "/T_UM_MatLUT_Global", "class": "Texture2D",
         "settings": dict(POINT_NO_MIPS, compression_settings="TC_HDR")},
        {"file": INPUTS / "textures" / "T_UM_MatID_Legacy.png", "asset": TEX + "/T_UM_MatID_Legacy", "class": "Texture2D",
         "settings": dict(POINT_NO_MIPS, compression_settings="TC_GRAYSCALE")},
        {"file": INPUTS / "textures" / "T_UM_Test_MatIDChecker.png", "asset": ROOT + "/Test/T_UM_Test_MatIDChecker",
         "class": "Texture2D", "settings": dict(POINT_NO_MIPS, compression_settings="TC_GRAYSCALE")},
        {"file": INPUTS / "textures" / "T_UM_Test_BCChecker.png", "asset": ROOT + "/Test/T_UM_Test_BCChecker",
         "class": "Texture2D", "settings": {"compression_settings": "TC_DEFAULT", "srgb": True}},
        {"file": INPUTS / "textures" / "T_UM_Test_EdgeRamp.png", "asset": ROOT + "/Test/T_UM_Test_EdgeRamp",
         "class": "Texture2D", "settings": {"compression_settings": "TC_GRAYSCALE", "srgb": False}},
    ]
    for s in specs:
        s["file"] = str(s["file"]).replace("\\", "/")
    return specs


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def task(ue: Ue, script: str, out_dir: Path, timeout=900, **kw):
    return ue.run_task(str(HERE / "ue" / script), str(out_dir / "_task.json"), timeout=timeout, **kw)


def write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=1, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8",
                    newline="\n")


def cmd_import(ue: Ue, out: Path, a) -> dict:
    specs = texture_specs()
    for s in specs:
        if not Path(s["file"]).is_file():
            raise SystemExit("missing %s: run build_ue_inputs.py first" % s["file"])
    res = task(ue, "um_v2_import.py", out, textures=specs, delete_dirs=[ROOT + "/_probe"])
    res["inputs_sha256"] = {Path(s["file"]).name: sha(Path(s["file"])) for s in specs}
    res["specs"] = specs
    return res


def cmd_v1check(ue: Ue, out: Path, a) -> dict:
    res = {"files": {}}
    for f in V1_FILES:
        p = CONTENT / f
        res["files"][f] = sha(p)
    base = json.loads(Path(a.v1_baseline).read_text(encoding="utf-8")) if a.v1_baseline else None
    if base:
        res["baseline"] = a.v1_baseline
        res["unchanged"] = {f: base["files"].get(f) == h for f, h in res["files"].items()}
    res["dirty_in_editor"] = {}
    for f in V1_FILES:
        pkg = "/Game/" + f[:-len(".uasset")]
        res["dirty_in_editor"][pkg] = ue.call("asset", "is_dirty", {"asset_path": pkg}, record=False)
    return res


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("command", choices=["import", "master", "scene", "v1check", "stats"])
    ap.add_argument("--report", required=True, help="output directory for the report JSON (and frames)")
    ap.add_argument("--v1-baseline", help="v1check: an earlier v1check report to compare with")
    ap.add_argument("--tag", default="r1")
    a = ap.parse_args()
    out = Path(a.report).resolve()
    out.mkdir(parents=True, exist_ok=True)
    ue = Ue()
    started = now()
    if a.command == "import":
        res = cmd_import(ue, out, a)
    elif a.command == "v1check":
        res = cmd_v1check(ue, out, a)
    elif a.command == "stats":
        res = task(ue, "um_v2_stats.py", out, materials=[
            "/Game/UM/Materials/M_UM_Figure", ROOT + "/M_UM_Figure_v2", ROOT + "/MI_UM_Figure_v2_Template",
            ROOT + "/Test/MI_UM_v2_Test_Checker_UV1"])
    elif a.command == "master":
        from ue_v2_master import cmd_master
        res = cmd_master(ue, out, a, task)
    else:
        from ue_v2_scene import cmd_scene
        res = cmd_scene(ue, out, a, task)
    res = {"schema": "unmatched.um-v2-%s/1" % a.command, "tool": "tools/art/material_library/ue_v2.py",
           "command": a.command, "tag": a.tag, "started_at": started, "finished_at": now(), **res}
    tmp = out / "_task.json"
    if tmp.exists():
        tmp.unlink()
    write(out / ("um-v2-%s-report.json" % a.command), res)
    print(json.dumps({k: v for k, v in res.items() if k not in ("specs",)}, ensure_ascii=False)[:3000])
    return 0


if __name__ == "__main__":
    sys.exit(main())
