#!/bin/sh
# VC C1: A/B of Medusa's rest cap (a) + the base digit (c), fresh editor -Bench K1+K2x1.6+K2x2.5
cd /c/tmp/wt-visual
run() { name=$1; map=$2; shift 2
  python tools/art/render/live_tune.py bench --map $map --views K1+K2x1.6+K2x2.5 --out C:/tmp/visual/VC/C1/ab/$name "$@" > C:/tmp/visual/VC/C1/ab/$name.out 2>&1
  echo "$name exit=$?"; }
mkdir -p C:/tmp/visual/VC/C1/ab
run marm-a marmoreal --extra=-S08FaceCapMedusa=20 --extra=-S08BaseDigitCentre=0.60
run marm-b marmoreal --extra=-S08FaceCapMedusa=10 --extra=-S08BaseDigitCentre=0.60 --extra=-S08BaseDigitTurn=-15
run marm-c marmoreal --extra=-S08FaceCapMedusa=30 --extra=-S08BaseDigitCentre=0.60 --extra=-S08BaseDigitEm=0.95
run sarp-a sarpedon --extra=-S08FaceCapMedusa=20
