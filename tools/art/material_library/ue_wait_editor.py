"""Wait until the shared live UnrealEditor is free for a review (open level not dirty and not the P1.7 review level).

    python tools/art/material_library/ue_wait_editor.py [--timeout-s 3600] && python ... review ...

Parallel look-dev tasks share one editor and the same control level; a review refuses to start while another one has
the level open (dirty). This only polls (MCP get_current_level / is_dirty) and never changes anything. After the level
became free it waits `--settle-s` and checks again, so a review that is between two level loads is not overrun.
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tripo-pipeline" / "review"))
from ue_live import Ue  # noqa: E402

LEVEL = "/Game/ArtTests/P17ControlScene/L_P17ControlScene"


def free(ue):
    lv = ue.call("scene", "get_current_level", record=False)
    dirty = ue.call("asset", "is_dirty", {"asset_path": lv}, record=False)
    return (not dirty and not lv.startswith(LEVEL)), lv, dirty


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--timeout-s", type=float, default=3600)
    ap.add_argument("--settle-s", type=float, default=20)
    a = ap.parse_args()
    ue = Ue()
    t0 = time.time()
    while time.time() - t0 < a.timeout_s:
        ok, lv, dirty = free(ue)
        if ok:
            time.sleep(a.settle_s)
            ok, lv, dirty = free(ue)
            if ok:
                print("editor free:", lv, flush=True)
                return 0
        print(time.strftime("%H:%M:%S"), "busy:", lv, "dirty" if dirty else "", flush=True)
        time.sleep(20)
    print("timeout", flush=True)
    return 1


if __name__ == "__main__":
    sys.exit(main())
