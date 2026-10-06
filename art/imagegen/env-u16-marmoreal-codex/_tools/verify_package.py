"""Independent read-back verification. Writes only verification inside package."""
from pathlib import Path
import hashlib,json
import numpy as np
from PIL import Image
ROOT=Path(__file__).resolve().parents[4]
PKG=ROOT/'art/imagegen/env-u16-marmoreal-codex'
IMG=ROOT/'scraped-data/derived/env-u16-marmoreal-codex'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def run():
 v=json.loads((PKG/'verification.json').read_text(encoding='utf-8'))
 b=np.asarray(Image.open(ROOT/'scraped-data/derived/concepts/env-v1/marmoreal-v1.png').convert('RGB'))
 im=Image.open(IMG/'marmoreal-clean.png');a=np.asarray(im)
 field=np.asarray(Image.open(IMG/'marmoreal-field-mask.png'))
 remove=np.asarray(Image.open(IMG/'marmoreal-remove-mask.png'))
 frame=np.asarray(Image.open(IMG/'comparison/painted-frame-protection.png'))>0
 changed=np.any(a!=b,axis=2)
 records=json.loads((PKG/'generation-records.json').read_text(encoding='utf-8'))
 raw=[]
 for rec in records['generations']:
  raw.append({'variant':rec['variant'],'raw_bytes_unchanged':sha(ROOT/rec['raw_file'])==rec['raw_sha256'],'prompt_bytes_unchanged':sha(ROOT/rec['prompt_file'])==rec['prompt_sha256'],'input_bytes_unchanged':sha(ROOT/rec['input'])==rec['input_sha256']})
  # Actual tool argument is file text without leading/trailing whitespace.
  rec['submitted_prompt_normalization']='UTF-8 file text, CRLF preserved, leading/trailing whitespace trimmed'
  rec['submitted_prompt_sha256']=hashlib.sha256((ROOT/rec['prompt_file']).read_bytes().decode('utf-8').strip().encode('utf-8')).hexdigest()
  if rec['variant']=='A-R2':
   guide=IMG/'concepts/EN-01-A-R2-location-guide.png'
   rec['supporting_inputs']=[{'file':guide.relative_to(ROOT).as_posix(),'sha256':sha(guide),'role':'location and neighbouring cold paint guide only'}]
 (PKG/'generation-records.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 before=json.loads((PKG/'source-hashes-before.json').read_text(encoding='utf-8'))['files']
 hud={p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
 source_ok=all((ROOT/p).is_file() and sha(ROOT/p)==info['sha256'] for p,info in before.items()) and hud=={p for p in before if p.startswith('art/imagegen/hud-icons-v3/')}
 checks={'RGB_1672x941':im.mode=='RGB' and im.size==(1672,941),'field_binary_8bit':Image.open(IMG/'marmoreal-field-mask.png').mode=='L' and set(np.unique(field))=={0,255},'field_all_808080':bool(np.all(a[field==255]==128)),
 'outside_mask_zero':int(np.count_nonzero(changed&(remove==0)))==0,'outside_diff_black':bool(np.all(np.asarray(Image.open(IMG/'comparison/08-diff-outside-remove-mask.png'))==0)),
 'painted_frame_pixel_identical':bool(np.all(a[frame]==b[frame])),'door_interior_pixel_identical':bool(np.all(a[0:99,803:867]==b[0:99,803:867])),
 'source_unchanged':source_ok,'unretouched_generations':all(x['raw_bytes_unchanged'] for x in raw),'prompt_records_intact':all(x['prompt_bytes_unchanged'] and x['input_bytes_unchanged'] for x in raw),'budget_max_four':len(raw)<=4}
 v['independent_readback']={'checks':checks,'generation_hash_checks':raw,'passed':all(checks.values())}
 v['source_unchanged']=source_ok
 v['repository_outside_folder']=[]
 # The built-in generator stages its outputs outside the project; do not hide this.
 v['outside_folder']=[r['tool_managed_source'] for r in records['generations']]
 v['write_scope']='Agent-controlled repository writes: two authorised roots only. Built-in imagegen automatically created the listed cache PNGs under CODEX_HOME; this is an unmet strict nothing-else-on-disk condition. Those tool-managed originals were not edited or deleted.'
 cache_limit='Built-in imagegen created provider-managed cache PNGs outside the authorised roots; all deliverables were copied byte-for-byte into the derived package.'
 if cache_limit not in v['limits']:v['limits'].append(cache_limit)
 v['acceptance_pass']=all(checks.values()) and not v['limits'] and v.get('visual_review',{}).get('performed',False)
 (PKG/'verification.json').write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 print(json.dumps({'readback':checks,'acceptance_pass':v['acceptance_pass'],'limits':v['limits']},ensure_ascii=False))
if __name__=='__main__':run()
