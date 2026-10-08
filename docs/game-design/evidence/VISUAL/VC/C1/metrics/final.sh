#!/bin/sh
# VC C1: fresh editor -Bench K1+K2x1.6+K2x2.5 with the shipped profile (final) + the face-cap rollback
cd /c/tmp/wt-visual
run() { name=$1; map=$2; shift 2
  python tools/art/render/live_tune.py bench --map $map --views K1+K2x1.6+K2x2.5 --out C:/tmp/visual/VC/C1/runs/$name "$@" > C:/tmp/visual/VC/C1/runs/$name.out 2>&1
  echo "$name exit=$?"; }
run marmoreal-final marmoreal
run sarpedon-final sarpedon
run marmoreal-caplegacy marmoreal --extra=-S08FaceCapLegacy
echo FINAL-DONE
