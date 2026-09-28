#!/bin/bash
# One SYNTX image2video run (5 s, no audio) for a hero motion reference (art/animation-refs/<ASSET-ID>/<CUE>/).
# WARNING: a real run SPENDS SYNTX tokens. The script quotes the price first (get-model-info, free) into
# run_<Cue>/quote.json and refuses to run when the quote exceeds SYNTX_MAX_COST.
#
# usage: gen.sh <Cue> <promptfile>        e.g. gen.sh LungeAttack art/animation-refs/ASSET-MEDUSA-001/MED-LungeAttack/prompt.txt
#        <Cue> only names the scratch run dir run_<Cue>/ (use a unique name per run, e.g. ARTH-Idle, MED-HitReact-take2).
# env:
#   SYNTX_WORK     scratch dir for raw responses (default C:/tmp/medusa-vid). Raw files contain the account id and
#                  private storage URLs: keep them OUTSIDE the repo, copy with import_runs.py (redacts them).
#   SYNTX_FILEOBJ  upload-files result object for the input image (default $SYNTX_WORK/fileobj.json);
#                  get it with: cd art/imagegen/mvp-v1/characters && node $SYNTX_MCP upload-files
#                  '{"files":[{"path":"ref-medusa-v5-front.png"}],"model_type":"kling_image2video"}'
#                  (path must be under cwd: MCP_FILE_ROOTS default), then save .files[0] without "status"/"preview".
#   SYNTX_CHAT_ID  SYNTX chat uuid (2026-09-28 Medusa runs: 5ac4e224-2019-46c2-b4a2-8d5804835b0e)
#   SYNTX_MCP      path to syntx_mcp.cjs (default C:/Users/ren/.claude/mcp-servers/clients/syntx_mcp.cjs)
#   SYNTX_MODEL    kling25std (default: Kling 2.5 image2video, mode standart, 6 tokens on 2026-09-28)
#                  | seedance15pro720 (Seedance 1.5 Pro, 720p, no audio, 7.5) | seedancefast480 (Seedance 1.0 Pro-Fast
#                  480p, 6) | hailuo23fast768 (Hailuo 2.3 Fast 768p, 6 s, 9). Prices: quote of 2026-09-28, re-quoted
#                  on every run.
#   SYNTX_MAX_COST refuse to generate when the quoted cost is higher (default 10)
#   DRY_RUN=1      only write run_<Cue>/req.json; no quote/balance/generation/wait calls, no spend.
#
# Differences from the scratch C:/tmp/medusa-vid/gen.sh used on 2026-09-28: chat id, input URL, work dir and
# client path are parameters instead of literals (the literal URL contained the account id); DRY_RUN, the
# result.json extraction and the mp4 download (lines after balance_after) were added. 2026-09-28 (hero refs):
# SYNTX_MODEL, the pre-run quote (quote.json) and SYNTX_MAX_COST were added. The Kling request body (req.json)
# is built the same way: a DRY_RUN with syntx-session/fileobj.json reproduces MED-<Cue>/syntx/req.json.
set -u
cue=$1; pf=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
WORK=${SYNTX_WORK:-C:/tmp/medusa-vid}
FILEOBJ=${SYNTX_FILEOBJ:-$WORK/fileobj.json}
MCP=${SYNTX_MCP:-C:/Users/ren/.claude/mcp-servers/clients/syntx_mcp.cjs}
S="node $MCP"
PATCH=$(cd "$(dirname "$0")" && (pwd -W 2>/dev/null || pwd))/patch.cjs   # Windows form for node --require
MODEL=${SYNTX_MODEL:-kling25std}
MAXC=${SYNTX_MAX_COST:-10}
CHAT=${SYNTX_CHAT_ID:?set SYNTX_CHAT_ID}
[ -f "$FILEOBJ" ] || { echo "missing $FILEOBJ"; exit 1; }
FILEOBJ=$(cd "$(dirname "$FILEOBJ")" && pwd)/$(basename "$FILEOBJ")
case $MODEL in
  kling25std)       QX='{"version":"2.5","native_audio":"false"}'; QA='{"ai_name":"kling","model_type":"kling_image2video","mode":"standart","video_duration":5}';;
  seedance15pro720) QX='{"resolution":"720p","generate_audio":"false"}'; QA='{"ai_name":"seedance","model_type":"seedance-1.5-pro","video_duration":5}';;
  seedancefast480)  QX='{"resolution":"480p"}'; QA='{"ai_name":"seedance","model_type":"seedance_pro-fast","video_duration":5}';;
  hailuo23fast768)  QX='{"resolution":"768p"}'; QA='{"ai_name":"hailuo-minimax","model_type":"hailuo-2.3-fast","video_duration":6}';;
  *) echo "unknown SYNTX_MODEL $MODEL"; exit 1;;
esac
cd "$WORK" || exit 1
mkdir -p run_$cue
if [ "$MODEL" = kling25std ]; then
python - "$pf" "$CHAT" "$FILEOBJ" > run_$cue/req.json <<'PY'
import json,sys
pf,chat,fo=sys.argv[1:]
p=open(pf,encoding='utf-8').read().strip()
obj=json.load(open(fo,encoding='utf-8'))
print(json.dumps({"ai_name":"kling","chat_id":chat,"prompt":p,"model_type":"kling_image2video","file_urls":[obj["url"]],
 "model_settings":{"version":"2.5","mode":"standart","video_duration":5,"native_audio":False,"file_urls":[obj]}}))
PY
else
python - "$pf" "$CHAT" "$FILEOBJ" "$MODEL" > run_$cue/req.json <<'PY'
import json,sys
pf,chat,fo,model=sys.argv[1:]
p=open(pf,encoding='utf-8').read().strip()
obj=json.load(open(fo,encoding='utf-8'))
# Seedance defaults (seen in result.json of MED-HitReact take3, 2026-09-28): aspect_ratio 16:9 and camera_fixed false ->
# the 1:1 input was cropped and the camera zoomed out during the first second; so both are set explicitly.
ai,mt,ms={'seedance15pro720':('seedance','seedance-1.5-pro',{"resolution":"720p","video_duration":5,"generate_audio":False,
                                                             "aspect_ratio":"1:1","camera_fixed":True}),
          'seedancefast480':('seedance','seedance_pro-fast',{"resolution":"480p","video_duration":5,"aspect_ratio":"1:1",
                                                             "camera_fixed":True}),
          'hailuo23fast768':('hailuo-minimax','hailuo-2.3-fast',{"resolution":"768p","video_duration":6})}[model]
ms["file_urls"]=[obj]
print(json.dumps({"ai_name":ai,"chat_id":chat,"prompt":p,"model_type":mt,"file_urls":[obj["url"]],"model_settings":ms}))
PY
fi
[ $? -eq 0 ] || { echo "req.json build failed"; exit 1; }
[ "${DRY_RUN:-0}" = "1" ] && { echo "dry run: $WORK/run_$cue/req.json"; exit 0; }
SYNTX_EXTRA_Q="$QX" NODE_OPTIONS="--require $PATCH" $S get-model-info "$QA" 2>/dev/null > run_$cue/quote.json
cost=$(python -c "import json;print(json.loads(json.load(open('run_$cue/quote.json',encoding='utf-8'))['content'][0]['text'])['cost'])") \
  || { echo "quote failed"; cat run_$cue/quote.json; exit 1; }
python -c "import sys;sys.exit(0 if float('$cost')<=float('$MAXC') else 1)" || { echo "quote $cost > SYNTX_MAX_COST $MAXC, not generating"; exit 1; }
echo "quote $MODEL: $cost"
$S get-balance '{}' 2>/dev/null > run_$cue/balance_before.json
$S generate-video @run_$cue/req.json 2>/dev/null > run_$cue/gen.json || { echo "gen failed"; cat run_$cue/gen.json; exit 1; }
python -c "import json,sys;sys.exit(1 if json.load(open('run_$cue/gen.json',encoding='utf-8')).get('isError') else 0)" \
  || { echo "gen error"; cat run_$cue/gen.json; $S get-balance '{}' 2>/dev/null > run_$cue/balance_after.json; exit 1; }
$S wait-for-response "{\"chat_id\":\"$CHAT\",\"timeout\":540000,\"poll_interval\":10000}" 2>/dev/null > run_$cue/wait.json; echo "wait exit $?"
$S get-balance '{}' 2>/dev/null > run_$cue/balance_after.json
# result.json = media[0] of wait.json (task_id, object_url, payload.settings, payload.prompt, width, height).
# On 2026-09-28 this extraction and the download were separate steps that were not kept; import_runs.py checks
# that the kept result.json files equal this derivation. The mp4 is then copied by hand to
# art/animation-refs/<ASSET-ID>/<CUE>/<CUE>_<model>_ref.mp4.
python - run_$cue/wait.json > run_$cue/result.json <<'PY2'
import json,sys
t=json.load(open(sys.argv[1],encoding='utf-8'))['content'][0]['text']
m=json.loads(t.split('--- media ---')[1].split('--- metadata ---')[0])[0]; md=m['metadata']
print(json.dumps({'task_id':md['task_id'],'url':m['object_url'],'settings':md['payload']['settings'],
 'prompt':md['payload']['prompt'],'width':md['width'],'height':md['height']},indent=1))
PY2
url=$(python -c "import json;print(json.load(open('run_$cue/result.json'))['url'])")
curl -sSL "$url" -o run_$cue/out.mp4 && echo "saved $WORK/run_$cue/out.mp4"
