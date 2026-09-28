#!/usr/bin/env bash
# Full headless chain of the ASSET-PLACEHOLDER-MANNEQUIN Blender stage (no Tripo, no UE, no live Blender).
# Usage (repo root, Git Bash): bash art/pipeline-candidates/ASSET-PLACEHOLDER-MANNEQUIN/scripts/run_mannequin.sh [run-id]
set -euo pipefail
export MSYS_NO_PATHCONV=1
A=art/pipeline-candidates/ASSET-PLACEHOLDER-MANNEQUIN
R=$A/${1:-20260928-blender-um-fbx-v1}
P=$A/build-profiles/mannequin-parametric-um-fbx-v1.json
B=${BLENDER:-"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"}
W=$(pwd -W 2>/dev/null || pwd)
mkdir -p "$R/logs" "$R/work/deform"
BL() { "$B" -b --factory-startup --python-exit-code 1 --python "$@"; }
# 1) build twice: the second run must give byte-identical FBX
BL $A/scripts/build_mannequin.py -- "$W/$P" "$W/$R" > "$R/logs/build.log" 2>&1
sha256sum "$R"/export/*.fbx > "$R/logs/fbx-sha-run1.txt"
BL $A/scripts/build_mannequin.py -- "$W/$P" "$W/$R" > "$R/logs/build-repeat.log" 2>&1
sha256sum "$R"/export/*.fbx | diff - "$R/logs/fbx-sha-run1.txt" && echo "FBX byte-identical on rebuild" | tee "$R/logs/determinism.txt"
# 2) independent read-back + the stock static-prop check
BL $A/scripts/readback_fbx.py -- "$W/$R" "$W/$P" "$W/$R/reports/fbx-readback.json" > "$R/logs/readback.log" 2>&1
BL tools/tripo-pipeline/blender/check_static_prop_fbx.py -- "$W/$R/export/SM_PlaceholderMannequin.fbx" \
   "$W/$R/reports/check_static_prop_fbx-SM_PlaceholderMannequin.json" 0.5 > "$R/logs/check_static_prop_fbx-SM_PlaceholderMannequin.log" 2>&1
BL tools/tripo-pipeline/blender/check_static_prop_fbx.py -- "$W/$R/export/SM_PlaceholderMannequin_Base.fbx" \
   "$W/$R/reports/check_static_prop_fbx-SM_PlaceholderMannequin_Base.json" 0.225 > "$R/logs/check_static_prop_fbx-SM_PlaceholderMannequin_Base.log" 2>&1
# 3) rig_deform_probe on the authored .blend and on the FBX turned back to the authored frame (Harpy helper)
"$B" -b --factory-startup --python art/pipeline-candidates/ASSET-HARPY-001/scripts/fbx_to_authored_blend.py -- \
   "$W/$R/export/SK_PlaceholderMannequin.fbx" "$W/$R/work/probe-fbx-authored.blend" > "$R/logs/fbx_to_authored.log" 2>&1
"$B" -b --factory-startup --python tools/tripo-pipeline/anim/rig_deform_probe.py -- "$W/$R/work/mannequin.blend" "$W/$R/work/deform" mannequin-blend > "$R/logs/deform-blend.log" 2>&1
"$B" -b --factory-startup --python tools/tripo-pipeline/anim/rig_deform_probe.py -- "$W/$R/work/probe-fbx-authored.blend" "$W/$R/work/deform" mannequin-fbx > "$R/logs/deform-fbx.log" 2>&1
python tools/tripo-pipeline/anim/overlay_bones.py "$R/work/deform" mannequin-blend
python tools/tripo-pipeline/anim/overlay_bones.py "$R/work/deform" mannequin-fbx
# 4) previews (EEVEE) + FBX round-trip frame, then measurements and JPEG <= 1200 px
BL $A/scripts/render_previews.py -- "$W/$R" "$W/$P" > "$R/logs/previews.log" 2>&1
BL $A/scripts/render_previews.py -- "$W/$R" "$W/$P" --fbx > "$R/logs/previews-fbx.log" 2>&1
python $A/scripts/postprocess_previews.py "$R"
grep -h "MANNEQUIN_BUILD_OK\|MANNEQUIN_READBACK\|DEFORM_OK\|MANNEQUIN_PREVIEWS" "$R"/logs/*.log
