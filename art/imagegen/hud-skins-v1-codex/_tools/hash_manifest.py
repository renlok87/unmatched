"""Hash ALL package/derived files, except this manifest itself. No other writes."""
import hashlib
import json
from pathlib import Path
P = Path(__file__).resolve().parents[1]
R = P.parents[2]
D = R/'scraped-data/derived/hud-skins-v1-codex'
out = P/'manifest-sha256.json'
files = {p.relative_to(R).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for root in (P,D) for p in sorted(root.rglob('*')) if p.is_file() and p!=out}
out.write_text(json.dumps({'algorithm':'sha256','excluded':[out.relative_to(R).as_posix()],'files':files},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert all(hashlib.sha256((R/k).read_bytes()).hexdigest()==v for k,v in files.items())
print('Manifest verified:',len(files),'files')
