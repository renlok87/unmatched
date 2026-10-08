#!/usr/bin/env bash
# usage: measure.sh <map> <tag> [baseline tag]
set -u
MAP=$1; TAG=$2; BASE=${3:-on-base}
R=C:/tmp/visual/VS8/A1/runs
cd /c/tmp/wt-visual
PYTHONIOENCODING=utf-8 python tools/art/render/hero_light_metrics.py measure --off $R/$MAP-off --on $R/$MAP-$TAG --mask-body $R/$MAP-maskbody --mask-fig $R/$MAP-maskfig --baseline $( [ "$BASE" = p9 ] && echo C:/tmp/wt-visual/docs/game-design/evidence/ENV-MAPS/p9b-hero-light-detail-2026-10-02/$MAP-p9 || echo $R/$MAP-$BASE ) --d6 docs/game-design/evidence/ENV-MAPS/p9b-hero-light-detail-2026-10-02/d6-config.json --board $MAP --label $MAP-$TAG --json C:/tmp/visual/VS8/A1/metrics/$MAP-$TAG${OUTSFX:-}.json > /dev/null 2>&1; echo "measure rc=$?"
mkdir -p C:/tmp/visual/VS8/A1/metrics
