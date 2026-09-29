#!/usr/bin/env bash
# ADDING-AN-ASSET.md iteration 3: commands copied from the instruction (sections 0, 1.1, 3, 4.1, 5, 11), placeholders filled:
#   <ASSET-ID>.<PART>=ASSET-DECOR-KIT-001.BARREL  <run>=20260928-p17-repro  <SM_Name>=SM_Decor_Barrel  <Asset>=DecorBarrel
#   <source-spec>=art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json
#   <прежний run>=art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel
#   <профиль-образец>=art/pipeline-candidates/ASSET-DECOR-KIT-001/build-profiles/decor-barrel-static-um-fbx-v1.json
#   <evidence>=docs/art-pipeline/evidence/p17-control-scene-2026-09-28   <task>=t31
set -euo pipefail
cd C:/Users/ren/WebstormProjects/unmached/unmached
# §0
export MSYS_NO_PATHCONV=1
export PYTHONIOENCODING=utf-8
T="python tools/tripo-pipeline/tripo_pipeline.py"
B="C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"
git -c core.longpaths=true status --short | wc -l
# §1.1
python tools/tripo-pipeline/validate_registry.py | tail -1
# §1.2: already paid Tripo tasks -> §1.3-1.4 and §2 skipped (0 credits)
# §3.2
python art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/restore_embedded_textures.py | tail -1
# §4.1
R=art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p17-repro
python -c "import json,sys; s=json.load(open(sys.argv[1],encoding='utf-8')); [print(f['role'], f['path']) for f in s['files']]" art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json
# §4.1.1
$T init --run-dir $R/ue-passthrough --asset-id ASSET-DECOR-KIT-001.BARREL --primary-source tripo-3f7a258f \
    --primary-role smartuv-tex2k-pbr-glb --export-basename SM_Decor_Barrel_TripoPassthrough --run-id 20260928-p17-repro-ue-passthrough
$T register-source --run-dir $R/ue-passthrough --spec art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json
$T run --run-dir $R/ue-passthrough
# §4.1.2
mkdir -p $R/reports
python -c "import json,sys,pathlib; p=json.load(open(sys.argv[1],encoding='utf-8')); p['out_dir']=sys.argv[3]; pathlib.Path(sys.argv[2]).write_bytes((json.dumps(p,indent=2,ensure_ascii=False)+chr(10)).encode('utf-8'))" art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel/reports/candidate-params.json $R/reports/candidate-params.json $R
"$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/static_prop_candidate.py -- $R/reports/candidate-params.json > C:/tmp/t31/repro3/blender-candidate.log 2>&1
"$B" -b --factory-startup --python-exit-code 1 --python tools/tripo-pipeline/blender/check_static_prop_fbx.py -- $R/export/SM_Decor_Barrel.fbx $R/reports/fbx-readback.json 0.5 > C:/tmp/t31/repro3/blender-readback.log 2>&1
python -c "import json,sys; r=json.load(open(sys.argv[1],encoding='utf-8')); print([k for k,v in r['checks'].items() if v is not True], r['checks_passed'])" $R/reports/candidate-report.json
# §4.1.3
python -c "import json,sys,pathlib; p=json.load(open(sys.argv[1],encoding='utf-8')); p['profile_id']=sys.argv[3]; p['candidate']['dir']=sys.argv[4]; pathlib.Path(sys.argv[2]).write_bytes((json.dumps(p,indent=1,ensure_ascii=False)+chr(10)).encode('utf-8'))" art/pipeline-candidates/ASSET-DECOR-KIT-001/build-profiles/decor-barrel-static-um-fbx-v1.json art/pipeline-candidates/ASSET-DECOR-KIT-001/build-profiles/decor-barrel-static-um-fbx-v1-p17-repro.json decor-barrel-static-um-fbx-v1-p17-repro/1 $R
# §4.1.4
$T init --run-dir $R/ue-candidate --asset-id ASSET-DECOR-KIT-001.BARREL --primary-source tripo-3f7a258f \
    --primary-role smartuv-tex2k-pbr-glb --export-basename SM_Decor_Barrel --run-id 20260928-p17-repro-ue-candidate \
    --profile static-candidate --build-profile art/pipeline-candidates/ASSET-DECOR-KIT-001/build-profiles/decor-barrel-static-um-fbx-v1-p17-repro.json
$T register-source --run-dir $R/ue-candidate --spec art/pipeline-candidates/ASSET-DECOR-KIT-001/source-specs/tripo-3f7a258f.json
$T run --run-dir $R/ue-candidate
# §5.1 (snapshots of the repeat go to <evidence>/repro)
EV=docs/art-pipeline/evidence/p17-control-scene-2026-09-28
mkdir -p $EV/repro
python tools/tripo-pipeline/review/ue_content_snapshot.py $EV/repro/snapshot-before.json --extra-folder /Game/ArtTests --extra-folder /Game/S08 | tail -3
# §5.2 (§4.1 step 5 folders)
for pair in "ue-passthrough:Passthrough" "ue-candidate:Candidate"; do
  run=${pair%%:*}; sub=${pair##*:}
  $T --backend mcp ue-import --run-dir $R/$run --ue-folder /Game/PipelineCandidates/DecorBarrel/20260928-p17-repro/$sub
  $T --backend mcp ue-import --run-dir $R/$run
  $T --backend mcp ue-import --run-dir $R/$run --force
  $T --backend mcp ue-import --run-dir $R/$run
done
# §5.4
python tools/tripo-pipeline/review/ue_content_snapshot.py $EV/repro/snapshot-after.json --compare $EV/repro/snapshot-before.json --extra-folder /Game/ArtTests --extra-folder /Game/S08 | grep -A2 protected_unchanged
# §11
python tools/tripo-pipeline/review/control_scene.py --out C:/tmp/t31/cs --tag repro --only barrel --barrel /Game/PipelineCandidates/DecorBarrel/20260928-p17-repro/Candidate/Meshes/SM_Decor_Barrel | tail -2
python tools/tripo-pipeline/review/control_scene_analyze.py --runs C:/tmp/t31/cs --tags r1 r2 r3 --repro-tag repro --out $EV
python tools/tripo-pipeline/review/repro_compare.py --base art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p15-barrel --repro art/pipeline-candidates/ASSET-DECOR-KIT-001/20260928-p17-repro --frames $EV/repro-frames.json --out $EV/repro/repro-report.json
echo "== iteration 3 done"
