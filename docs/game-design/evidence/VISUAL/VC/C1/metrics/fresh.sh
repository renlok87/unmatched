#!/usr/bin/env bash
# usage: fresh.sh <map> <run name> [profiles json|-] [extra flags, space separated] : one fresh live-tune session, first shot only (= fresh -Bench poses)
set -u
MAP=$1; NAME=$2; PROF=${3:--}; EXTRA=${4:-}
cd /c/tmp/wt-visual
ARGS=(start --map $MAP)
[ "$PROF" != "-" ] && ARGS+=(--profiles "$PROF")
for E in $EXTRA; do ARGS+=("--extra=$E"); done
timeout 400 python tools/art/render/live_tune.py "${ARGS[@]}" > C:/tmp/visual/VC/C1/start-$NAME.json 2>&1; echo "$NAME start rc=$?"
rm -rf C:/tmp/visual/VC/C1/runs/$NAME
timeout 300 python tools/art/render/live_tune.py shot --views K1+K2x1.6+K2x2.5 --out C:/tmp/visual/VC/C1/runs/$NAME --tag $NAME > C:/tmp/visual/VC/C1/shot-$NAME.json 2>&1; echo "$NAME shot rc=$?"
timeout 120 python tools/art/render/live_tune.py stop > /dev/null 2>&1; echo "$NAME stop rc=$?"
