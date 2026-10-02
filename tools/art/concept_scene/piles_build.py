"""ENV-MAPS P8.1 piles (ASSET-ENV-S-PROPS-001 / SM_Env_S_Piles): the painted bay piles with their rope spans, the stern
lantern pole and the two rope-bound posts on the front cliff by the waterfall.

  python -B tools/art/concept_scene/piles_build.py         # -> <work>/SM_Env_S_Piles.pre.npz + reports/piles-build.json

Same builder as palisade_build.py (C0 pixels -> vertical logs on the island, rope bands, catenary rope spans);
params piles.groups / piles.ropes. The lantern hosts of design.json (post-bay, post-stern) are piles here, so the
layout hangs the lanterns on real posts.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
import palisade_build as PB  # noqa: E402

if __name__ == "__main__":
    sys.exit(PB.run("piles", "SM_Env_S_Piles", "MI_Env_S_Piles", "piles-build.json"))
