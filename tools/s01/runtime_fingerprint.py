import datetime, hashlib, json, pathlib, subprocess
root = pathlib.Path(__file__).resolve().parents[2]
evidence = root/'docs/game-design/evidence/S01'
source = pathlib.Path(r'C:\Users\ren\WebstormProjects\unmached\unmached')
before = json.loads((evidence/'provenance.json').read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
changed = [f['path'] for f in before['sourceDirtyTrackedFiles'] if sha(source/f['path'])!=f['sourceSha256']]
assert not changed, f'Source changed since preflight: {changed}'
files = []
for p in sorted((source/'backend/dist/src').rglob('*.js')):
    files.append({'path':str(p.relative_to(source)).replace('\\','/'),'sha256':sha(p),'lastWriteUtc':datetime.datetime.fromtimestamp(p.stat().st_mtime,datetime.timezone.utc).isoformat()})
result = {'capturedUtc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'sourceUnchangedSincePreflight':True,
    'sourceHead':subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip(),
    'compiledJavaScriptFiles':files,'warning':'On-disk hashes. Process PID changed externally from 47592 to 122224 at 08:00:12Z; capture rerun after this fingerprint. No process restart performed by S01 harness.'}
(evidence/'runtime-fingerprint.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'{len(files)} compiled modules fingerprinted. Source tracked dirty file hashes unchanged.')
