"""Mark props of a map-kit run as built from their env_kit build reports (status.json stage built + build block).

    python tools/mapkits/mark_built.py <map> <key>... [--run <run dir>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "mapkits"))
import mapkit  # noqa: E402
import tripo_intake as ti  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("map"); ap.add_argument("keys", nargs="+"); ap.add_argument("--run")
    a = ap.parse_args()
    st = mapkit.load_status(a.map)
    for key in a.keys:
        e = st["props"][key]
        run = a.run or (e.get("tripo") or {}).get("run")
        n = ti.ue_name(a.map, key)
        rep = ROOT / run / "reports" / "assets" / f"SM_Env_{n}.build.json"
        b = json.loads(rep.read_text(encoding="utf-8"))
        ok = bool(b.get("checks_passed"))
        e["build"] = {"fbx": f"{run}/export/SM_Env_{n}.fbx", "tris": b["roundtrip"]["triangles"], "checks": ok,
                      "dimsUu": b["scale_pivot"]["dimensions_uu_ue_xyz"], "report": str(rep.relative_to(ROOT)).replace("\\", "/")}
        if ok:
            e["stage"] = "built"
        print(key, ok, b["roundtrip"]["triangles"], b["scale_pivot"]["dimensions_uu_ue_xyz"])
    mapkit.save_status(a.map, st)


if __name__ == "__main__":
    main()
