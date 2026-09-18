"""Read-only inventory. No environment values, account credentials or tokens."""
import hashlib, json, pathlib, subprocess, datetime
root = pathlib.Path(__file__).resolve().parents[2]
source = pathlib.Path(r'C:\Users\ren\WebstormProjects\unmached\unmached')
out = root / 'docs/game-design/evidence/S01'
def git(base, *args):
    return subprocess.check_output(['git', '-c', 'core.safecrlf=false', '-C', str(base), *args], text=True, encoding='utf-8', stderr=subprocess.DEVNULL).strip()
def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else None
paths = git(source, 'diff', '--name-only').splitlines()
report = {
    'capturedUtc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'sourceRoot': str(source), 'worktreeRoot': str(root),
    'sourceHead': git(source, 'rev-parse', 'HEAD'),
    'initialWorktreeHead': '0641577c96ca5bcc4baa2285ea1ba9046a76ffca',
    'alignedWorktreeHead': git(root, 'rev-parse', 'HEAD'),
    'sourceDirtyTrackedFiles': [{
        'path': p, 'sourceSha256': sha(source / p), 'baselineSha256': sha(root / p),
        'copied': False,
    } for p in paths],
    'copiedDocumentation': ['docs/game-design', 'docs/unreal', 'docs/backend-api'],
    'policy': 'Source untouched. Runtime uses original backend/dist; commit alone is not deployed identity. No dirty implementation files copied.'
}
out.mkdir(parents=True, exist_ok=True)
(out / 'provenance.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(f'Provenance: {len(paths)} dirty tracked files inventoried, no implementation overlays.')
