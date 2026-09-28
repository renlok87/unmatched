#!/bin/bash
# One SYNTX -> Kling 2.5 image2video run (mode standart, 5 s, no audio) for an ASSET-MEDUSA-001 motion reference.
# WARNING: a real run SPENDS SYNTX tokens (quote on 2026-09-28: 6 per run). Quote first with patch.cjs.
#
# usage: gen.sh <Cue> <promptfile>        e.g. gen.sh LungeAttack art/animation-refs/ASSET-MEDUSA-001/MED-LungeAttack/prompt.txt
# env:
#   SYNTX_WORK     scratch dir for raw responses (default C:/tmp/medusa-vid). Raw files contain the account id and
#                  private storage URLs: keep them OUTSIDE the repo, copy with import_runs.py (redacts them).
#   SYNTX_FILEOBJ  upload-files result object for the input image (default $SYNTX_WORK/fileobj.json);
#                  get it with: cd art/imagegen/mvp-v1/characters && node $SYNTX_MCP upload-files
#                  '{"files":[{"path":"ref-medusa-v5-front.png"}],"model_type":"kling_image2video"}'
#                  (path must be under cwd: MCP_FILE_ROOTS default), then save .files[0] without "status"/"preview".
#   SYNTX_CHAT_ID  SYNTX chat uuid (2026-09-28 runs: 5ac4e224-2019-46c2-b4a2-8d5804835b0e)
#   SYNTX_MCP      path to syntx_mcp.cjs (default C:/Users/ren/.claude/mcp-servers/clients/syntx_mcp.cjs)
#   DRY_RUN=1      only write run_<Cue>/req.json; no balance/generation/wait calls, no spend.
#
# Differences from the scratch C:/tmp/medusa-vid/gen.sh used on 2026-09-28: chat id, input URL, work dir and
# client path are parameters instead of literals (the literal URL contained the account id); DRY_RUN, the
# result.json extraction and the mp4 download (lines after balance_after) were added. The request body (req.json)
# is built the same way: a DRY_RUN with syntx-session/fileobj.json reproduces MED-<Cue>/syntx/req.json.
set -u
cue=$1; pf=$(cd "$(dirname "$2")" && pwd)/$(basename "$2")
WORK=${SYNTX_WORK:-C:/tmp/medusa-vid}
FILEOBJ=${SYNTX_FILEOBJ:-$WORK/fileobj.json}
S="node ${SYNTX_MCP:-C:/Users/ren/.claude/mcp-servers/clients/syntx_mcp.cjs}"
CHAT=${SYNTX_CHAT_ID:?set SYNTX_CHAT_ID}
[ -f "$FILEOBJ" ] || { echo "missing $FILEOBJ"; exit 1; }
FILEOBJ=$(cd "$(dirname "$FILEOBJ")" && pwd)/$(basename "$FILEOBJ")
cd "$WORK" || exit 1
mkdir -p run_$cue
python - "$pf" "$CHAT" "$FILEOBJ" > run_$cue/req.json <<'PY'
import json,sys
pf,chat,fo=sys.argv[1:]
p=open(pf,encoding='utf-8').read().strip()
obj=json.load(open(fo,encoding='utf-8'))
print(json.dumps({"ai_name":"kling","chat_id":chat,"prompt":p,"model_type":"kling_image2video","file_urls":[obj["url"]],
 "model_settings":{"version":"2.5","mode":"standart","video_duration":5,"native_audio":False,"file_urls":[obj]}}))
PY
[ $? -eq 0 ] || { echo "req.json build failed"; exit 1; }
[ "${DRY_RUN:-0}" = "1" ] && { echo "dry run: $WORK/run_$cue/req.json"; exit 0; }
$S get-balance '{}' 2>/dev/null > run_$cue/balance_before.json
$S generate-video @run_$cue/req.json 2>/dev/null > run_$cue/gen.json || { echo "gen failed"; cat run_$cue/gen.json; exit 1; }
$S wait-for-response "{\"chat_id\":\"$CHAT\",\"timeout\":540000,\"poll_interval\":10000}" 2>/dev/null > run_$cue/wait.json; echo "wait exit $?"
$S get-balance '{}' 2>/dev/null > run_$cue/balance_after.json
# result.json = media[0] of wait.json (task_id, object_url, payload.settings, payload.prompt, width, height).
# On 2026-09-28 this extraction and the download were separate steps that were not kept; import_runs.py checks
# that the kept result.json files equal this derivation. The mp4 is then copied by hand to
# art/animation-refs/ASSET-MEDUSA-001/MED-<Cue>/MED-<Cue>_kling25_ref.mp4.
python - run_$cue/wait.json > run_$cue/result.json <<'PY2'
import json,sys
t=json.load(open(sys.argv[1],encoding='utf-8'))['content'][0]['text']
m=json.loads(t.split('--- media ---')[1].split('--- metadata ---')[0])[0]; md=m['metadata']
print(json.dumps({'task_id':md['task_id'],'url':m['object_url'],'settings':md['payload']['settings'],
 'prompt':md['payload']['prompt'],'width':md['width'],'height':md['height']},indent=1))
PY2
url=$(python -c "import json;print(json.load(open('run_$cue/result.json'))['url'])")
curl -sSL "$url" -o run_$cue/out.mp4 && echo "saved $WORK/run_$cue/out.mp4"
