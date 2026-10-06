"""Final text/filesystem integrity audit after verification; only package writes."""
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path
P = Path(__file__).resolve().parents[1]
R = P.parents[2]
D = R/'scraped-data/derived/hud-skins-v1-codex'
def read(p):
    return json.loads(p.read_text(encoding='utf-8'))
def dump(p,data):
    assert p.resolve().is_relative_to(P)
    p.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
dump(P/'process-audit.json',{
    'run':'CX-02r',
    'all_started_build_and_verifier_sessions_observed_exit_code':True,
    'completed_exec_session_ids':[30719,70928,98096,22486],
    'unreal_or_service_started':False,
    'background_process_launches':0,
    'process_inventory':{'method':'Get-CimInstance Win32_Process read-only query','result':'Access denied by environment (HRESULT 0x80041003). No process was stopped. All owned build/verifier exec sessions had already returned exit_code=0.'}
})
report = read(P/'verification.json')
failed = [k for k,v in report['acceptance'].items() if not v['passed']]
assert failed==['enabled_edge_contrast_to_panel_bg'],failed
assert report['source_unchanged'] and report['outside_folder']==[]
assert all(hashlib.sha256((R/k).read_bytes()).hexdigest()==v for k,v in read(P/'source-hashes-before.json')['files'].items())
assert len(report['gray']['pairs'])==450 and not report['gray']['failed_pairs']
assert report['palette']['opaque_outside_deltaE76_3']==0
assert set(p.name for p in D.iterdir())=={'backgrounds','comparison'}
assert len(list((P/'concepts').iterdir()))==1
assert len(list((P/'concepts').rglob('*.png')))==87
assert all(p.name in ('vector','masters') for p in next((P/'concepts').iterdir()).iterdir())
assert not any('cursor' in p.name.lower() for root in (P,D) for p in root.rglob('*'))
review = (P/'_tools/claude-review-verbatim.md').read_bytes()
assert (P/'README.md').read_bytes().endswith(review)
assert hashlib.sha256(review).hexdigest()==read(P/'fix1-provenance.json')['claude_review_sha256']
def scan():
    records = {}
    for root in (P,D):
        for p in root.rglob('*'):
            if p.suffix in ('.md','.json'):
                text = p.read_text(encoding='utf-8')
                if p.suffix=='.json':
                    json.loads(text)
                records[p.relative_to(R).as_posix()] = {'cyrillic_characters':len(re.findall('[\u0400-\u04ff]',text)),'double_question_runs':len(re.findall(r'\?{2,}',text)),'utf8_valid':True}
    return records
report['text_encoding'] = scan()
assert all(v['double_question_runs']==0 for v in report['text_encoding'].values())
dump(P/'verification.json',report)
assert scan()==report['text_encoding']
subprocess.run([sys.executable,'-B',str(P/'_tools/hash_manifest.py')],check=True)
assert scan()==report['text_encoding']
manifest = read(P/'manifest-sha256.json')
actual = {p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for root in (P,D) for p in root.rglob('*') if p.is_file() and p!=P/'manifest-sha256.json'}
assert actual==manifest['files']
print(json.dumps({'final_integrity_passed':True,'hashed_files':len(actual),'png_files':len(report['exports']),'text_files':len(report['text_encoding']),'failed_acceptance':failed,'primary_disabled_text_contrast':next(v['ratio'] for v in report['contrast']['primary_text'] if v['state']=='BtnPrimary_Disabled'),'derived_bytes':sum(p.stat().st_size for p in D.rglob('*') if p.is_file())},indent=2))
