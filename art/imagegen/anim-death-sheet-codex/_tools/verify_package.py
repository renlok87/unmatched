"""Independent AN-30 artifact checks, no renderer import and no outside writes."""
import sys
sys.dont_write_bytecode=True
import hashlib
import json
import re
from pathlib import Path
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

P=Path(__file__).resolve().parents[1]
ROOT=P.parents[2]
def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def save(name,value):
    path=(P/name).resolve()
    assert path.is_relative_to(P)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

before=json.loads((P/'source-hashes-before.json').read_text(encoding='utf-8'))
after=json.loads((P/'source-hashes-after.json').read_text(encoding='utf-8'))
for group in ['inputs','hud_icons_v3']:
    assert before[group]==after[group]
    for name,record in before[group].items():
        assert sha(ROOT/name)==record['sha256'],name
assert sha(P/'_tools/draw_icons_v3_snapshot.py')==sha(ROOT/'art/imagegen/hud-icons-v3/_tools/draw_icons.py')

master=Image.open(P/'vector/AN-30-death-sheet.png')
assert master.size==(1920,1080) and master.mode=='RGBA'
actual=np.array(master)
gray_checks=[]
for path in (P/'comparison').glob('*-gray.png'):
    color=P/'vector/AN-30-death-sheet.png' if path.name=='AN-30-death-sheet-gray.png' else path.with_name(path.name.replace('-gray.png','.png'))
    a=np.array(Image.open(color));b=np.array(Image.open(path))
    y=np.rint(.2126*a[:,:,0]+.7152*a[:,:,1]+.0722*a[:,:,2]).astype('uint8')
    assert all(np.array_equal(b[:,:,i],y) for i in range(3))
    assert np.array_equal(a[:,:,3],b[:,:,3])
    gray_checks.append(path.name)

embers=[]
for actor,base,factor,team in [('KingArthur',565,.46,(232,192,106)),('Harpy',777,.59,(90,127,159))]:
    src=Image.open(P/f'traces/{actor}-f21-q34-mask.png').resize((round(420*factor),)*2,Image.Resampling.NEAREST)
    m=np.array(src)>0;yy,xx=np.where(m);lo=int(yy.min());hi=int(yy.max()+1)
    for cx,progress in [(1496,.35),(1780,.70)]:
        front=hi-round((hi-lo)*progress)
        y0=base-hi+front+8
        crop=actual[y0:base,cx-70:cx+70,:3]
        mask=np.all(crop==team,axis=2)
        labs,count=ndi.label(mask);areas=np.bincount(labs.ravel())
        dots=[int(v) for v in areas[1:] if 4<=v<=40]
        assert len(dots)==10,(actor,progress,dots)
        embers.append({'actor':actor,'progress':progress,'connected_ember_dots':len(dots)})
assert sum(e['connected_ember_dots'] for e in embers)==40

# Plain fade must keep every body pixel and use a single uniform opacity.
fade=np.array(Image.open(P/'comparison/AN-30-ash-vs-fade.png'))
fade_checks=[]
cream=(249,235,219,255);navy=(6,22,35,255)
for actor,base in [('KingArthur',603),('Harpy',1020)]:
    ref=fade[base-176:base+1,280:520,:3]
    body=np.all(ref==cream[:3],axis=2)
    assert body.sum()>1000
    for cx,progress in [(850,.35),(1300,.70),(1750,1)]:
        opacity=round(255*(1-progress))
        bg=Image.new('RGBA',(1,1),navy)
        fg=Image.new('RGBA',(1,1),cream[:3]+(opacity,))
        expected=Image.alpha_composite(bg,fg).getpixel((0,0))[:3]
        sample=fade[base-176:base+1,cx-120:cx+120,:3]
        assert np.all(sample[body]==expected),(actor,progress)
    fade_checks.append({'actor':actor,'body_preserved':True,'uniform_opacity':True})

timing=json.loads((P/'reports/timing.json').read_text(encoding='utf-8'))
assert timing['hero']['gone']==sum([450,875,300,500])==2125
assert timing['sidekick']['gone']==sum([450,875,0,400])==1725
assert timing['hero']['result']==timing['hero']['gone']+1000==3125
assert timing['cue']['fallen_heart']==1100
assert timing['sidekick']['result'] is None
assert not timing['skip_cuts_clip'] and not timing['skip_cuts_dissolve']
readme=(P/'README.md').read_text(encoding='utf-8')
for link in re.findall(r'\]\(([^)]+)\)',readme):
    # The manifest is deliberately written last, after verification.json.
    if link!='manifest-sha256.json':
        assert (P/link).resolve().exists(),link
assert '**предложено**' in readme
report={'task':'AN-30','passed':True,'source_entries_rehashed':len(before['inputs'])+len(before['hud_icons_v3']),
        'before_after_equal':True,'master_rgba_1920x1080':True,'gray_exports_verified':sorted(gray_checks),
        'embers_counted_from_final_png':embers,'plain_fade_checked_from_final_png':fade_checks,
        'timing_arithmetic':True,'readme_links_exist':True,'outside_folder':[],
        'process_cleanup':'Rendering/check commands run in foreground and exit; no clients, services or background builds were started.'}
save('reports/final-checks.json',report)
v=json.loads((P/'verification.json').read_text(encoding='utf-8'))
v.setdefault('independent_artifact_checks',{}).update(report)
v['write_audit']['written_files']=sorted(p.relative_to(ROOT).as_posix() for p in P.rglob('*') if p.is_file())
save('verification.json',v)
from fix1_checks import extend_checks, write_manifest
extend_checks(P,ROOT,v,save,sha)
# All metadata including verification and README must precede this final write.
write_manifest(P,ROOT,save,sha)
assert (P/'manifest-sha256.json').exists()
sys.stdout.reconfigure(encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
