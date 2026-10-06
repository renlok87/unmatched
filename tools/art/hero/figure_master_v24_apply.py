"""AN-32 (BP-16): rebuild M_UM_Figure_v2 as v2.4 - the Fix group of the look tuning.

    python tools/art/hero/figure_master_v24_apply.py          # rebuild the master in place, saved, report C:/tmp/an32

The Fix group (FixClassA/B 0..15 / -1 = off, FixGainA/B x BaseColor, FixSpecA/B + specular) is applied inside
UM_V2_Core by the same MatID decode that picks the LUT row (tools/art/material_library/ue/um_v2_core.hlsl). The
rebuild goes through the existing editor builder (tools/art/material_library/ue/um_v2_master.py) exactly like
tools/art/de011/de011.py apply; "instances" is empty, so no hero MI, no dissolve MIC and no test MI is touched -
they inherit the neutral defaults (class -1 / gain 1 / spec 0) and compile the v2.3 output bit for bit.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "tools" / "art" / "material_library"))
sys.path.insert(0, str(REPO / "tools" / "art" / "de010"))
import de010  # noqa: E402
sys.path.insert(0, str(REPO / "tools" / "art" / "de011"))
import de011  # noqa: E402
import ue_v2_master as vm  # noqa: E402

WORK = Path("C:/tmp/an32")
FIX_PARAMS = ["FixClassA", "FixGainA", "FixSpecA", "FixClassB", "FixGainB", "FixSpecB"]


def main() -> int:
    WORK.mkdir(parents=True, exist_ok=True)
    g = vm.figure_v2_graph(vm.load_spec())
    sig = vm.graph_signature(g)
    master = {"master": vm.MASTER, "settings": vm.SETTINGS, "nodes": g.nodes, "links": g.links, "attrs": g.attrs,
              "instances": [], "signature": sig, "out": str(WORK / "apply-master.json")}
    res = de010.run_editor(REPO / "tools" / "art" / "de011" / "de011_apply_ue.py",
                           {"out": str(WORK / "apply.json"), "master": master,
                            "master_script": str(vm.HERE / "ue" / "um_v2_master.py"),
                            "switch": vm.DISSOLVE_SWITCH, "mics": []},
                           WORK, "apply")
    res["master"].update(graph_signature=sig, node_count=len(g.nodes), link_count=len(g.links),
                         core_hlsl_sha256=hashlib.sha256(vm.CORE_HLSL.read_bytes()).hexdigest())
    de010.write(WORK / "apply.json", res)
    params = res["master"].get("parameters", {})
    have = [p for p in FIX_PARAMS if p in params.get("scalar", [])]
    ok = (not res["master"].get("compile_errors") and len(have) == len(FIX_PARAMS) and
          str(res["master"].get("blend_mode", "")).endswith("BLEND_OPAQUE"))
    print(json.dumps({"ok": ok, "fix_params": have, "compile_errors": res["master"].get("compile_errors"),
                      "statistics": res["master"].get("statistics")}, indent=1))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
