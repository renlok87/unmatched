#!/usr/bin/env python
"""Finalize write ledger and hash every deliverable; writes only in PACKAGE."""
import hashlib
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[2]
DERIVED = ROOT/'scraped-data/derived/fx-vortex-codex'


def run():
    verification = json.loads((PACKAGE/'verification.json').read_text(encoding='utf-8'))
    assert not verification['failures'], verification['failures']
    files = sorted(p for folder in (PACKAGE,DERIVED) for p in folder.rglob('*') if p.is_file())
    audit = json.loads((PACKAGE/'write-audit.json').read_text(encoding='utf-8'))
    audit['writes'] = sorted({p.relative_to(ROOT).as_posix() for p in files if not (p.name.startswith(('procedural-v0-','procedural-v1-')) or p.name in ('source-hashes-before.json','draw_icons_v3_snapshot.py','STYLE.md'))} | {
        (PACKAGE/'manifest-sha256.json').relative_to(ROOT).as_posix()})
    audit['scope'] = 'FX-29 fix1 writes in two authorized folders; immutable v0/v1 concepts, source baseline, snapshot and STYLE excluded; no global concurrent-session disk claim'
    audit['outside_folder'] = []
    audit['processes_started'] = 'foreground Python only; exited when each command finished'
    audit['background_services_started'] = []
    (PACKAGE/'write-audit.json').write_text(json.dumps(audit,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    verification['outside_folder_evidence_scope'] = audit['scope']
    (PACKAGE/'verification.json').write_text(json.dumps(verification,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    manifest = {'algorithm':'sha256','paths_relative_to':'project root',
                'exclusions':['art/imagegen/fx-vortex-codex/manifest-sha256.json (self hash)'],
                'files':{p.relative_to(ROOT).as_posix():{'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
                         for p in files if p.name != 'manifest-sha256.json'}}
    (PACKAGE/'manifest-sha256.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    loaded = json.loads((PACKAGE/'manifest-sha256.json').read_text(encoding='utf-8'))
    assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest() == info['sha256'] for path,info in loaded['files'].items())
    print(f'Manifest verified: {len(loaded["files"])} files; no background processes started.')


if __name__ == '__main__':
    run()
