#!/usr/bin/env bash
# H2 bake of one hero, all stages in order (Git Bash on Windows). Every Blender stage is headless (-b --factory-startup);
# nothing touches the live Blender sessions (:9876/:9877) or UE.
#
#   tools/tripo-pipeline/blender/h2_bake_harpy/run_all.sh <profile.json> <run_dir> [--from STAGE] [--to STAGE] [--cpu]
#
# Stages: import lowpoly shape uv uvcheck bake textures rig seethrough probe review. Logs go to <run>/logs/<stage>.log.
#   shape      preview_lowpoly.py: high-poly vs game-mesh silhouettes (preview/shape, IoU)
#   seethrough see_through.py: one-sided game-camera gate (reports/see-through.json; fails the run above the gate)
#              + k2_projection.py (reports/k2-projection.json) + nape_visibility.py (H2.1: visible neck-cap pixels,
#              reports/nape-visibility.json)
#   review21   (H2.1, optional, needs H2_BASELINE=<harpy-h2-bake/2 run copy>) review_h21.py: concept | H2 | H2.1 sheets
#              and the K2 5x / 1.6x game frames of both
set -euo pipefail
export MSYS_NO_PATHCONV=1
PROFILE=$(cd "$(dirname "$1")" && pwd -W)/$(basename "$1")
RUN=$(mkdir -p "$2" && cd "$2" && pwd -W)
shift 2
FROM=import
TO=review
CPU=""
while [ $# -gt 0 ]; do
  case "$1" in
    --from) FROM=$2; shift 2 ;;
    --to) TO=$2; shift 2 ;;
    --cpu) CPU=--cpu; shift ;;
    *) echo "unknown option $1"; exit 2 ;;
  esac
done
HERE=$(cd "$(dirname "$0")" && pwd -W)
REPO=$(cd "$HERE/../../../.." && pwd -W)
B=${BLENDER:-"C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"}
PY=${PYTHON:-python}
mkdir -p "$RUN/logs" "$RUN/reports" "$RUN/preview" "$RUN/export" "$RUN/textures" "$RUN/work"
PREV=$($PY -c "import json,sys;print(json.load(open(sys.argv[1],encoding='utf-8'))['review']['previous_candidate_run'])" "$PROFILE")
STAGES=(import lowpoly shape uv uvcheck bake textures rig seethrough probe review review21)
run=0
blender_stage() {  # stage script args...
  local log="$RUN/logs/$1.log"; shift
  "$B" -b --factory-startup --python "$@" > "$log" 2>&1
  grep -q "H2_BAKE_STAGE_OK\|CLIP_VALIDATION PASS\|FBX_AUTHORED_OK\|SHEET_OK" "$log" || { echo "stage failed, see $log"; exit 1; }
  if grep -q "Windows fatal exception" "$log"; then echo "fatal exception in $log"; exit 1; fi
}
for s in "${STAGES[@]}"; do
  [ "$s" = "$FROM" ] && run=1
  [ $run = 1 ] || continue
  echo "== $s"
  case "$s" in
    import)   blender_stage import "$HERE/stage_import.py" -- "$PROFILE" "$RUN" ;;
    lowpoly)  blender_stage lowpoly "$HERE/stage_lowpoly.py" -- "$PROFILE" "$RUN" ;;
    shape)    blender_stage preview-shape "$HERE/preview_lowpoly.py" -- "$RUN" "$RUN/preview/shape" ;;
    uv)       blender_stage uv "$HERE/stage_uv.py" -- "$PROFILE" "$RUN" ;;
    uvcheck)  $PY "$HERE/uv_check.py" "$PROFILE" "$RUN" > "$RUN/logs/uvcheck.log" 2>&1 ;;
    bake)     blender_stage bake "$HERE/stage_bake.py" -- "$PROFILE" "$RUN" $CPU ;;
    textures) $PY "$HERE/textures.py" "$PROFILE" "$RUN" > "$RUN/logs/textures.log" 2>&1 ;;
    rig)      blender_stage rig "$HERE/stage_rig.py" -- "$PROFILE" "$RUN" ;;
    seethrough)
      blender_stage see-through "$HERE/see_through.py" -- "$PROFILE" "$RUN"
      blender_stage k2-projection "$HERE/k2_projection.py" -- "$PROFILE" "$RUN"
      blender_stage nape-visibility "$HERE/nape_visibility.py" -- "$PROFILE" "$RUN" --frames "$RUN/work/nape-frames" --tag h21
      HOLD=$($PY -c "import json,sys;print(1 if 'see_through_holdout' in json.load(open(sys.argv[1],encoding='utf-8'))['review'] else 0)" "$PROFILE")
      if [ "$HOLD" = 1 ]; then
        blender_stage see-through-holdout "$HERE/see_through.py" -- "$PROFILE" "$RUN" --config-key see_through_holdout             --out "$RUN/reports/see-through-holdout.json" --frames "$RUN/preview/see-through-holdout" --no-gate
      fi
      ;;
    probe)
      SK=$(ls "$RUN"/export/SK_*.fbx | head -1)
      blender_stage fbx-authored "$REPO/art/pipeline-candidates/ASSET-HARPY-001/scripts/fbx_to_authored_blend.py" -- "$SK" "$RUN/work/probe-fbx-authored.blend"
      mkdir -p "$RUN/preview/deform"
      "$B" -b --factory-startup --python "$REPO/tools/tripo-pipeline/anim/rig_deform_probe.py" -- "$RUN/work/h2-candidate.blend" "$RUN/preview/deform" h2-blend > "$RUN/logs/deform-blend.log" 2>&1
      "$B" -b --factory-startup --python "$REPO/tools/tripo-pipeline/anim/rig_deform_probe.py" -- "$RUN/work/probe-fbx-authored.blend" "$RUN/preview/deform" h2-fbx > "$RUN/logs/deform-fbx.log" 2>&1
      $PY "$REPO/tools/tripo-pipeline/anim/overlay_bones.py" "$RUN/preview/deform" h2-blend > "$RUN/logs/overlay.log" 2>&1
      $PY "$REPO/tools/tripo-pipeline/anim/overlay_bones.py" "$RUN/preview/deform" h2-fbx >> "$RUN/logs/overlay.log" 2>&1
      "$B" -b --factory-startup --python "$REPO/tools/tripo-pipeline/anim/validate_clip.py" -- "$SK" --kind=skeletal-mesh \
          --character=Harpy "--out=$RUN/reports/validate-skeletal-mesh-v2.json" > "$RUN/logs/validate.log" 2>&1 || { echo "validate_clip FAIL"; exit 1; }
      ;;
    review)
      blender_stage review-concept "$HERE/review_h2.py" -- "$PROFILE" "$RUN" concept
      blender_stage review-k2 "$HERE/review_h2.py" -- "$PROFILE" "$RUN" k2 --prev-run "$REPO/$PREV"
      blender_stage review-instances "$HERE/review_h2.py" -- "$PROFILE" "$RUN" instances
      $PY "$REPO/art/pipeline-candidates/ASSET-HARPY-001/scripts/analyse_instances.py" "$RUN/preview/instances" > "$RUN/logs/instances-analysis.log" 2>&1
      $PY "$HERE/compose_review.py" "$PROFILE" "$RUN" > "$RUN/logs/compose.log" 2>&1
      ;;
    review21)
      if [ -z "${H2_BASELINE:-}" ]; then echo "review21 skipped (H2_BASELINE not set)"; else
        blender_stage nape-baseline "$HERE/nape_visibility.py" -- "$PROFILE" "$H2_BASELINE" --tag h2             --out "$RUN/reports/nape-visibility-h2-baseline.json" --frames "$RUN/work/nape-frames-h2"
        blender_stage see-through-baseline "$HERE/see_through.py" -- "$PROFILE" "$H2_BASELINE" --no-gate             --out "$RUN/reports/see-through-h2-baseline.json" --frames "$RUN/work/see-through-h2-baseline"
        blender_stage see-through-holdout-baseline "$HERE/see_through.py" -- "$PROFILE" "$H2_BASELINE" --no-gate             --config-key see_through_holdout --out "$RUN/reports/see-through-holdout-h2-baseline.json"             --frames "$RUN/work/see-through-holdout-h2-baseline"
        blender_stage review21-frames "$HERE/review_h21.py" -- "$PROFILE" "$RUN" "$H2_BASELINE"
        $PY "$HERE/compose_h21.py" "$PROFILE" "$RUN" > "$RUN/logs/compose-h21.log" 2>&1
      fi
      ;;
  esac
  [ "$s" = "$TO" ] && break
done
echo "H2 bake done: $RUN"
