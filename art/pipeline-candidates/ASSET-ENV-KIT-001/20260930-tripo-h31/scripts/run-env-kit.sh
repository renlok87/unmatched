#!/usr/bin/env sh
# Reproduce this run's ENV kit outputs (headless Blender on the CPU, no renders). Run from the repository root.
# Needs the raw Tripo GLBs in source/ (gitignored; sha256 pinned in reports/tripo-run.json) and the Tripo
# reference views in C:/tmp/envmaps-research/tripo-inputs/<ID>/ (outside git; sha256 pinned in
# reports/orientation-check.json).
set -e
python tools/art/env_kit/run_env_kit.py \
    --params art/pipeline-candidates/ASSET-ENV-KIT-001/20260930-tripo-h31/scripts/env-kit-params.json \
    --steps probe,orient,build,readback,report "$@"
