#!/usr/bin/env bash
# VC C1 measurement: fresh off / masks (Marmoreal), then one --tuner session (harpy-neutral profile): on-base + harpy iterations
cd /c/tmp/visual/VC/C1
./fresh.sh marmoreal marmoreal-off - -NoHeroLight
./fresh.sh marmoreal marmoreal-maskbody C:/tmp/visual/VC/C1/profiles/maskbody.json
./fresh.sh marmoreal marmoreal-maskfig C:/tmp/visual/VC/C1/profiles/maskfig.json
cd /c/tmp/wt-visual
timeout 400 python tools/art/render/live_tune.py start --map marmoreal --profiles C:/tmp/visual/VC/C1/profiles/harpy-neutral.json --tuner > C:/tmp/visual/VC/C1/start-marm-tune.json 2>&1; echo "tune start rc=$?"
cd /c/tmp/visual/VC/C1
./tune.sh marmoreal on-base
./tune.sh marmoreal i1 --set /lightProfiles/marmoreal-night/heroMaterials/Harpy/*/FixGainA=0.9
./tune.sh marmoreal i2 --set /lightProfiles/marmoreal-night/heroMaterials/Harpy/*/FixGainA=0.85
cd /c/tmp/visual/VC/C1
echo RUN1-DONE (tuner session left running)
