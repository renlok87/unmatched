"""Append one Tripo Studio spend to the shared credits ledger (tripo.window.entries).

tools/art/syntx_video_refs/ledger_append.py writes only syntx.window (it reads gen.sh JSON files), so Tripo UI spends
need this separate writer. Same file discipline: lock file, read-modify-write, temp file + os.replace, json indent 2,
ensure_ascii False, original line endings kept. Recomputes byTask[owner], spent, remaining, balanceEndUi.

usage: python tripo_ledger_append.py --history-time "2026-09-28 16:40:12" --op "..." --task-id <uuid>
           --quoted 55 --before 24335 --after 24280 --ref <repo path of tripo-run.json> --owner "<task label>"
           [--parent-task-id <uuid>] [--reason "<why a regeneration>"] [--dry-run]
The price (--quoted) must be read from the Studio button BEFORE the click. A duplicate (same task id + same op) is refused.
"""
import argparse
import datetime
import json
import os
import sys
import time

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))
LEDGER = os.environ.get('CREDITS_LEDGER') or os.path.join(REPO, 'docs', 'art-pipeline', 'evidence',
                                                           's3-baseline-2026-09-28', 'credits-ledger.json')


def main():
    ap = argparse.ArgumentParser()
    for k in ('--history-time', '--op', '--task-id', '--ref', '--owner'):
        ap.add_argument(k, required=True)
    for k in ('--quoted', '--before', '--after'):
        ap.add_argument(k, required=True, type=int)
    ap.add_argument('--parent-task-id')
    ap.add_argument('--reason')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    delta = a.after - a.before
    entry = {'historyTime': a.history_time,
             'observedAt': datetime.datetime.now().strftime('%Y-%m-%d %H:%M'),
             'op': a.op, 'taskId': a.task_id}
    if a.parent_task_id:
        entry['parentTaskId'] = a.parent_task_id
    entry.update({'delta': delta, 'quoted': a.quoted, 'balanceBefore': a.before, 'balanceAfter': a.after,
                  'ref': a.ref, 'owner': a.owner})
    if a.reason:
        entry['reason'] = a.reason
    if -delta != a.quoted:
        entry['note'] = 'списание %d не равно цене с кнопки %d — сверить с историей Studio' % (-delta, a.quoted)
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
        w = led['tripo']['window']
        if any(e.get('taskId') == a.task_id and e.get('op') == a.op for e in w['entries']):
            sys.exit('entry already in ledger: %s / %s' % (a.task_id, a.op))
        last = w.get('balanceEndUi')
        if last is not None and last != a.before:
            entry['gapNote'] = 'balanceEndUi журнала %s != баланс до %s: между ними чужие списания — разнести по истории' % (last, a.before)
        w['entries'].append(entry)
        by = w.setdefault('byTask', {})
        by[a.owner] = by.get(a.owner, 0) - delta
        w['spent'] = sum(-e['delta'] for e in w['entries'] if isinstance(e.get('delta'), (int, float)))
        if isinstance(w.get('limit'), (int, float)):
            w['remaining'] = w['limit'] - w['spent']
        w['balanceEndUi'] = a.after
        w['balanceEndSource'] = 'история Studio %s (%s), UI %s' % (a.history_time, a.op, a.after)
        text = (json.dumps(led, ensure_ascii=False, indent=2) + '\n').replace('\n', nl)
        if a.dry_run:
            print(json.dumps(entry, ensure_ascii=False, indent=1))
            return
        tmp = LEDGER + '.tmp'
        with open(tmp, 'w', encoding='utf-8', newline='') as f:
            f.write(text)
        os.replace(tmp, LEDGER)
        print('appended', a.task_id, a.op, delta)
    finally:
        os.close(fd)
        os.remove(lock)


if __name__ == '__main__':
    main()
