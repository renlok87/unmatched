"""Append one SYNTX spend (a gen.sh run) to the shared credits ledger, right after the run.

Usage: python tools/art/syntx_video_refs/ledger_append.py <scratch run dir> --asset ASSET-ID --cue CUE
                                                         --model LABEL --ref <repo dir> --owner TASK [--note TEXT]

Reads <run>/quote.json (price quoted before the run), balance_before.json, balance_after.json and, when present,
result.json (task id) or gen.json (failed generation). Appends an entry to syntx.window.entries of
docs/art-pipeline/evidence/s3-baseline-2026-09-28/credits-ledger.json and recomputes syntx.window.spent / remaining /
balanceEnd. The file is shared: read-modify-write under a lock file, written to a temp file and moved with
os.replace, so a concurrent writer never sees a half-written file; layout (json indent 2, line endings) is kept. No account ids are copied (balances only).
"""
import argparse
import datetime
import json
import os
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
LEDGER = os.environ.get('CREDITS_LEDGER') or os.path.join(REPO, 'docs', 'art-pipeline', 'evidence', 's3-baseline-2026-09-28',
                                                   'credits-ledger.json')


def text_json(path):
    return json.loads(json.load(open(path, encoding='utf-8'))['content'][0]['text'])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('run')
    ap.add_argument('--asset', required=True)
    ap.add_argument('--cue', required=True)
    ap.add_argument('--model', required=True)
    ap.add_argument('--ref', required=True)
    ap.add_argument('--owner', required=True)
    ap.add_argument('--note')
    a = ap.parse_args()
    quote = text_json(os.path.join(a.run, 'quote.json'))['cost']
    b0 = text_json(os.path.join(a.run, 'balance_before.json'))['balance']
    b1 = text_json(os.path.join(a.run, 'balance_after.json'))['balance']
    task_id, status = None, 'ok'
    rp = os.path.join(a.run, 'result.json')
    if os.path.exists(rp):
        task_id = json.load(open(rp, encoding='utf-8'))['task_id']
    else:
        status = 'нет result.json (генерация не завершилась или ошибка)'
    stamp = datetime.datetime.fromtimestamp(os.path.getmtime(os.path.join(a.run, 'balance_after.json'))).astimezone()
    entry = {'time': stamp.isoformat(timespec='seconds'), 'asset': a.asset, 'cue': a.cue, 'op': 'image2video (SYNTX)',
             'model': a.model, 'taskId': task_id, 'quotedBeforeRun': quote, 'balanceBefore': b0, 'balanceAfter': b1,
             'delta': round(b1 - b0, 2), 'owner': a.owner, 'ref': a.ref, 'status': status,
             'source': 'quote.json (get-model-info до запуска), balance_before/after.json (get-balance до/после)'}
    if a.note:
        entry['note'] = a.note
    lock = LEDGER + '.lock'
    for _ in range(300):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            time.sleep(0.2)
    else:
        sys.exit('ledger lock busy for 60 s: ' + lock)
    try:
        raw = open(LEDGER, encoding='utf-8', newline='').read()
        nl = '\r\n' if '\r\n' in raw else '\n'
        led = json.loads(raw)
        w = led['syntx']['window']
        if task_id and any(e.get('taskId') == task_id for e in w['entries']):
            sys.exit(f'task {task_id} already in ledger')
        w['entries'].append(entry)
        w['spent'] = round(sum(-e['delta'] for e in w['entries']), 2)
        w['remaining'] = round(w['limit'] - w['spent'], 2)
        w['balanceEnd'] = b1
        # same layout as the other writers of this file: json indent 2, ensure_ascii False, trailing newline,
        # original line endings kept
        text = (json.dumps(led, ensure_ascii=False, indent=2) + '\n').replace('\n', nl)
        tmp = LEDGER + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        os.replace(tmp, LEDGER)
    finally:
        os.close(fd)
        os.remove(lock)
    print(json.dumps(entry, ensure_ascii=False))


if __name__ == '__main__':
    main()
