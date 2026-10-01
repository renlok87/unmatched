#!/usr/bin/env sh
# Reproduce this run's ENV kit outputs (headless Blender -b --factory-startup -t 4 on the CPU at BELOW_NORMAL priority,
# no renders). Run from the repository root. Needs the raw Tripo GLBs in source/ (gitignored; sha256 pinned in
# reports/tripo-run.json) and the Tripo reference views in C:/tmp/envmaps-research/tripo-inputs5/<ID>/ (outside git;
# sha256 pinned in reports/orientation-check.json). ENV-M-CHERRY-V2 is not in the params (ENV-U13).
# Then: the looks (env_prop_look.py --check), the UE import plan (ue_import_env_kit.py --check), the layouts
# (scripts/p5_layout_props.py, layout_check.py) and ground_splat.py --write-layouts.
set -e
python tools/art/env_kit/run_env_kit.py \
    --params art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5/scripts/env-kit-params.json \
    --steps probe,orient,build,readback,report "$@"
python -B tools/art/env_kit/env_prop_look.py --check
python -B tools/art/env_kit/ue_import_env_kit.py --check > /dev/null
python -B art/pipeline-candidates/ASSET-ENV-KIT-001/20261001-tripo-h31-p5/scripts/p5_layout_props.py --check
python -B tools/art/env_kit/layout_check.py
