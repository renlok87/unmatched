"""Offline acceptance checks for the S01 evidence and local packaged artifact."""
import argparse, csv, hashlib, json, pathlib, re
root=pathlib.Path(__file__).resolve().parents[2]
parser=argparse.ArgumentParser()
parser.add_argument('--ue-artifact-root', type=pathlib.Path, default=root, help='Repository checkout containing the existing S01 packaged EXE')
args=parser.parse_args()
evidence=root/'docs/game-design/evidence/S01'
def load(path):return json.loads(path.read_text(encoding='utf-8-sig'))
tasks=load(evidence/'tasks.json')
assert set(tasks)=={f'GD-{i:03}' for i in range(1,6)}
for task,proof in tasks.items():
    assert proof['status']=='done'
    for artifact in proof['artifacts']:
        assert (evidence/artifact).is_file(), (task,artifact)
board=load(evidence/'content-board.json')['adminBoard']
fixture=load(evidence/'duel-start-p1.json')
projection={'board':{'width':board['width'],'height':board['height'],'cells':board['cells']},'fighters':[{k:f[k] for k in ['id','name','position','type']} for f in fixture['fighters']]}
imported=load(evidence/'ue/import-result.json')
assert imported['fixture_geometry_sha256']==hashlib.sha256(json.dumps(projection,sort_keys=True,separators=(',',':')).encode()).hexdigest()
assert imported['cells']==30 and imported['fighters']==6
assert all(abs(hi-lo-100)<.1 for lo,hi in zip(imported['min'],imported['max']))
assert abs(imported['min'][2])<.1 and imported['material_slots']==1
manifest=load(evidence/'ue/build-manifest.json')
exe=args.ue_artifact_root/manifest['packagedExecutable']
assert exe.is_file(), 'Rebuild with tools/s01/ue_build.ps1 to validate local executable'
assert exe.stat().st_size==manifest['executableBytes']
with exe.open('rb') as stream:
    assert hashlib.file_digest(stream,'sha256').hexdigest()==manifest['executableSha256']
assert manifest['smokeExitCode']==0 and 'api=http://localhost:3000/graphql' in manifest['smokeReady']
assert 'S01_SMOKE_COMPLETE' in manifest['smokeComplete']
runtime=(evidence/'ue/runtime-output.txt').read_text(encoding='utf-8-sig')
assert manifest['smokeReady'] in runtime and manifest['smokeComplete'] in runtime
combat=load(evidence/'combat-findings.json')
assert 'error' not in combat and 'cleanupError' not in combat
assert (evidence/'combat-defense.json').is_file(), 'This baseline claims a defense capture; missing on this random draw'
assert not (evidence/'live-error.json').exists() and not (evidence/'cleanup-error.json').exists()
assert (evidence/'duplicate-start.json').is_file(), 'Baseline claims duplicate-hero start was accepted'
for p in [root/'docs/game-design/README.md',root/'docs/game-design/13-sprint-plan.md',
          root/'docs/game-design/08-integration-decisions.md',root/'docs/game-design/11-open-questions-and-risks.md',
          evidence/'README.md',evidence/'rules-oracle.md']:
    for target in re.findall(r'\]\(([^)]+)\)',p.read_text(encoding='utf-8-sig')):
        if '://' not in target and not target.startswith('#'):
            linked=(p.parent/target.split('#')[0]).resolve()
            artifact_dir=(root/'unreal/Unmatched/Artifacts/S01').resolve()
            external_artifact=linked.is_relative_to(artifact_dir) and (args.ue_artifact_root/linked.relative_to(root)).is_file()
            assert linked.exists() or external_artifact, (p.name,target)
with (root/'docs/game-design/14-sprint-backlog.csv').open(encoding='utf-8-sig') as f:
    rows=list(csv.DictReader(f))
assert {r['id'] for r in rows if r['status']=='done'} >= set(tasks)
assert all(r['status']=='done' for r in rows if r['id'] in tasks)
print('PASS: task evidence references; live/UE geometry projection hash; imported cube bounds/pivot/material; EXE size/SHA256; standalone runtime markers; optional live outputs present; links; GD-001..005 remain done (later sprint statuses checked by package validator).')
