"""Copy raw SYNTX MCP responses of video-ref runs from scratch into the repo, redacting account ids.

Usage: python tools/art/syntx_video_refs/import_runs.py [--src C:/tmp/medusa-vid]      (the 2026-09-28 Medusa import)
       python tools/art/syntx_video_refs/import_runs.py --asset ASSET-KING-ARTHUR-001 --src C:/tmp/hero-vid/runs
              --session-src C:/tmp/hero-vid/king-arthur-v5 --run ARTH-Idle=ARTH-Idle --run ...
       python tools/art/syntx_video_refs/import_runs.py --asset ASSET-MEDUSA-001 --src C:/tmp/hero-vid/runs
              --no-session --run MED-HitReact-take2=MED-HitReact/take2

Source (written by gen.sh):  <src>/run_<Run>/{req,quote,gen,wait,result,balance_before,balance_after}.json (quote.json
                             only for runs after 2026-09-28 ~14:30), <session-src>/{chat,fileobj}.json,
                             <session-src>/models_*.json (catalog snapshot, list-models output; Medusa only).
Destination:                 art/animation-refs/<asset>/<dest>/syntx/<same names>   (default: MED-<Cue>/syntx/)
                             art/animation-refs/<asset>/syntx-session/<same names>
Redaction: "user_<digits>" in storage URLs/paths -> "user_REDACTED"; values of user_id/owner_id/author_id that look
like an account id (>= 10 digits) -> "REDACTED". Everything else (task ids, chat uuid, content hashes in URLs,
prompts, settings, balances) is kept. The MCP client never prints the API token; the script still fails if the
account id or a token-like field remains in any output file.
Checks: result.json equals media[0] of wait.json (same derivation as gen.sh).
"""
import argparse
import glob
import json
import os
import re
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
CUES = ['LungeAttack', 'Idle', 'HitReact', 'DeathSettle']
RUN_FILES = ['req.json', 'gen.json', 'wait.json', 'result.json', 'balance_before.json', 'balance_after.json']
OPTIONAL_RUN_FILES = ['quote.json']
ID_KEYS = ('user_id', 'owner_id', 'author_id')
RE_USER_PATH = re.compile(r'user_\d{6,}')
RE_ID_IN_TEXT = re.compile(r'("(?:user_id|owner_id|author_id)"\s*:\s*)"?\d{10,}"?')


def redact(o):
    if isinstance(o, dict):
        out = {}
        for k, v in o.items():
            if k in ID_KEYS and re.fullmatch(r'\d{10,}', str(v)):
                out[k] = 'REDACTED'
            else:
                out[k] = redact(v)
        return out
    if isinstance(o, list):
        return [redact(v) for v in o]
    if isinstance(o, str):
        return RE_ID_IN_TEXT.sub(r'\1"REDACTED"', RE_USER_PATH.sub('user_REDACTED', o))
    return o


def account_id(run_dir):
    t = json.load(open(os.path.join(run_dir, 'balance_before.json'), encoding='utf-8'))
    return str(json.loads(t['content'][0]['text'])['user_id'])


def result_from_wait(wait):
    t = wait['content'][0]['text']
    m = json.loads(t.split('--- media ---')[1].split('--- metadata ---')[0])[0]
    md = m['metadata']
    return {'task_id': md['task_id'], 'url': m['object_url'], 'settings': md['payload']['settings'],
            'prompt': md['payload']['prompt'], 'width': md['width'], 'height': md['height']}


def copy(src_path, dst_path, uid):
    obj = json.load(open(src_path, encoding='utf-8'))
    red = redact(obj)
    text = json.dumps(red, ensure_ascii=False, indent=1) + '\n'
    # guards: no account id (full or its float-rounded 16-digit prefix), no token-like keys
    assert uid[:12] not in text, f'account id left in {dst_path}'
    assert not re.search(r'"(?:api_key|token|authorization|access_token)"\s*:', text, re.I), f'token field in {dst_path}'
    os.makedirs(os.path.dirname(dst_path), exist_ok=True)
    with open(dst_path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)
    return os.path.relpath(dst_path, REPO).replace('\\', '/')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', default='C:/tmp/medusa-vid', help='parent of run_<Run>/ dirs')
    ap.add_argument('--asset', default='ASSET-MEDUSA-001')
    ap.add_argument('--run', action='append', default=[],
                    help='<Run>=<dest dir under art/animation-refs/<asset>/>; default: the four 2026-09-28 Medusa runs')
    ap.add_argument('--session-src', help='dir with chat.json, fileobj.json (and models_*.json); default --src')
    ap.add_argument('--no-session', action='store_true', help='do not copy session files (already imported)')
    a = ap.parse_args()
    asset_dir = os.path.join(REPO, 'art', 'animation-refs', a.asset)
    runs = [r.split('=', 1) for r in a.run] or [[c, f'MED-{c}'] for c in CUES]
    uid = account_id(os.path.join(a.src, f'run_{runs[0][0]}'))
    written = []
    for run, dest in runs:
        rd = os.path.join(a.src, f'run_{run}')
        wait = json.load(open(os.path.join(rd, 'wait.json'), encoding='utf-8'))
        res = json.load(open(os.path.join(rd, 'result.json'), encoding='utf-8'))
        assert result_from_wait(wait) == res, f'{run}: result.json != media[0] of wait.json'
        names = RUN_FILES + [n for n in OPTIONAL_RUN_FILES if os.path.exists(os.path.join(rd, n))]
        for n in names:
            written.append(copy(os.path.join(rd, n), os.path.join(asset_dir, dest, 'syntx', n), uid))
    if not a.no_session:
        ss = a.session_src or a.src
        for n in ['chat.json', 'fileobj.json'] + sorted(os.path.basename(p) for p in glob.glob(os.path.join(ss, 'models_*.json'))):
            written.append(copy(os.path.join(ss, n), os.path.join(asset_dir, 'syntx-session', n), uid))
    print('\n'.join(written))
    print(f'ok: {len(written)} files, account id redacted', file=sys.stderr)


if __name__ == '__main__':
    main()
