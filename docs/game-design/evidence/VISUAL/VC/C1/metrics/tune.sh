#!/usr/bin/env bash
# usage: tune.sh <map> <tag> [--set k=v ...] : in the running --tuner session apply the rows, shoot 3 views to runs/<map>-<tag>
set -u
MAP=$1; TAG=$2; shift 2
cd /c/tmp/wt-visual
if [ $# -gt 0 ]; then timeout 120 python tools/art/render/live_tune.py tune "$@" > C:/tmp/visual/VC/C1/tune-$MAP-$TAG.json 2>&1; echo "tune rc=$?"; fi
rm -rf C:/tmp/visual/VC/C1/runs/$MAP-$TAG
timeout 300 python tools/art/render/live_tune.py shot --views K1+K2x1.6+K2x2.5 --out C:/tmp/visual/VC/C1/runs/$MAP-$TAG --tag $TAG > C:/tmp/visual/VC/C1/shot-$MAP-$TAG.json 2>&1; echo "shot rc=$?"
