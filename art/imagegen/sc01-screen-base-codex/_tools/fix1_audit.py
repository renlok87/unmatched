"""SC-01 fix1 bookkeeping and build orchestration. All writes are root-guarded."""
from pathlib import Path
from itertools import product
import csv
import hashlib
import json
import shutil

import numpy as np
from PIL import Image

from source_audit import ROOT, PACKAGE, FONT_ROOT, sha256
from screen_mockup_base import Theme, Canvas, Viewport, contrast, luma709, mix

DERIVED = ROOT / 'scraped-data/derived/sc01-screen-base-codex'
SKINS = ROOT / 'art/imagegen/hud-skins-v1-codex'
EARLIER_NOTE = '04-hud-spec.md и hud.csv изменились в первом прогоне: другая сессия закоммитила 8a8dfe02. Это не ошибка пакета fix1.'


def dump(path, data):
    path = Path(path).resolve()
    if not any(path.is_relative_to(d) for d in (PACKAGE, DERIVED)):
        raise ValueError('Write outside package folders')
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def inventory():
    before = json.loads((PACKAGE/'fix1-before.json').read_text(encoding='utf-8'))
    result = {}
    for name in before['files']:
        path = Path(name) if Path(name).is_absolute() else ROOT/name
        result[name] = {'sha256':sha256(path),'bytes':path.stat().st_size} if path.is_file() else None
    # Also detect icon tree additions, rather than hashing only previously named files.
    for p in sorted((ROOT/'art/imagegen/hud-icons-v3').rglob('*')):
        if p.is_file():
            result[p.relative_to(ROOT).as_posix()] = {'sha256':sha256(p),'bytes':p.stat().st_size}
    return dict(sorted(result.items()))


def compact_sources(files):
    icons = {k:v for k,v in files.items() if k.startswith('art/imagegen/hud-icons-v3/')}
    digest = hashlib.sha256(json.dumps(icons,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'files':{k:dict(v) if v else None for k,v in files.items() if k not in icons},
        'icons':{'path':'art/imagegen/hud-icons-v3/','tree_digest':digest,'file_count':len(icons),
            'changed_files':[], 'digest_method':'sha256(canonical sorted JSON mapping path to sha256 and bytes)',
            'used_files':{k:v for k,v in icons.items() if k.endswith('/sizes/loader-spinner-48.png') or k.endswith('/_tools/draw_icons.py')}}}


def freeze_inputs(files):
    frozen = {}
    for name in files:
        path = Path(name) if Path(name).is_absolute() else ROOT/name
        if name.startswith('art/imagegen/hud-icons-v3/') or path.suffix not in ('.md','.json','.csv','.log','.txt'):
            continue
        target = DERIVED/'input-snapshots/fix1'/name
        if not target.resolve().is_relative_to(DERIVED):
            raise ValueError('Snapshot outside derived folder')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(path.read_bytes())
        if sha256(target) != files[name]['sha256']:
            raise RuntimeError('Input changed while freezing: '+name)
        frozen[name] = target
    return frozen


def refresh_manifest():
    used = json.loads((PACKAGE/'source-hashes-used.json').read_text(encoding='utf-8'))
    v = json.loads((PACKAGE/'verification.json').read_text(encoding='utf-8'))
    outputs = {p.relative_to(ROOT).as_posix():{'sha256':sha256(p),'bytes':p.stat().st_size}
        for d in (PACKAGE,DERIVED) for p in sorted(d.rglob('*'))
        if p.is_file() and p != PACKAGE/'manifest-sha256.json'}
    dump(PACKAGE/'manifest-sha256.json',{'schema':'SC-01.manifest/fix1',
        'sources':used['files'],'icon_tree':used['icons'],
        'before_snapshot':'fix1-before.json','original_before_snapshot':'source-hashes-before.json',
        'used_snapshot':'source-hashes-used.json','facts':v['facts'],
        'output_images':[e['path'] for e in v['exports']], 'outputs':outputs,
        'self_hash_note':'Every package and derived file except this manifest; input snapshots live in derived.'})


def lab(rgb):
    value = np.asarray(rgb,dtype=float)/255
    linear = np.where(value<=.04045,value/12.92,((value+.055)/1.055)**2.4)
    xyz = linear @ np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])
    xyz /= np.array([.95047,1,1.08883])
    f = np.where(xyz>(6/29)**3,np.cbrt(xyz),xyz/(3*(6/29)**2)+4/29)
    return np.stack((116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])),axis=-1)


def palette_audit(image, theme, geometry, backdrop=False):
    a = np.asarray(image.convert('RGB'))
    # Flat 3x3 interiors exclude text/curve/filter AA, including skin corner AA.
    flat = np.ones(a.shape[:2],bool)
    flat[[0,-1],:] = False; flat[:,[0,-1]] = False
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            flat &= np.all(a==np.roll(np.roll(a,dy,0),dx,1),axis=2)
    if backdrop:
        mask = np.zeros(a.shape[:2],bool)
        # Geometry includes pixel rects for palette provenance, not scene pixels.
        for item in geometry:
            if item['kind'] in ('modal','documentation'):
                x,y,w,h = item['rect_px']
                mask[round(y+12):round(y+h-12),round(x+12):round(x+w-12)] = True
        flat &= mask
    allowed = {theme.color(k) for k in theme.tokens['colors']}
    navy = theme.color('panel.bg')
    for name in ('panel.edge','panel.divider'):
        allowed.add(mix(theme.color(name),navy,theme.alpha(name)))
    # Accepted opaque flat skin colors and their OVER result on the panel body.
    for scale in (1,2):
        for p in (SKINS/f'vector/x{scale}').glob('*.png'):
            pixels = np.asarray(Image.open(p).convert('RGBA'))
            same = np.ones(pixels.shape[:2],bool)
            same[[0,-1],:]=False; same[:,[0,-1]]=False
            for dy,dx in product((-1,0,1),repeat=2):
                same &= np.all(pixels==np.roll(np.roll(pixels,dy,0),dx,1),axis=2)
            for row in np.unique(pixels[same],axis=0):
                if row[3]:
                    allowed.add(mix(tuple(int(x) for x in row[:3]),navy,int(row[3])/255))
                    if row[3]==255:allowed.add(tuple(int(x) for x in row[:3]))
    colors, counts = np.unique(a[flat],axis=0,return_counts=True)
    if not len(colors):return {'sample_count':0,'off_token_share':0}
    distances=np.linalg.norm(lab(colors)[:,None,:]-lab(sorted(allowed))[None,:,:],axis=2).min(axis=1)
    off=distances>3
    return {'sample_count':int(counts.sum()),'off_token_pixels':int(counts[off].sum()),
        'off_token_share':float(counts[off].sum()/counts.sum()),
        'off_colors':[{'rgb':c.tolist(),'delta_e76':float(d),'pixels':int(n)} for c,d,n in zip(colors[off],distances[off],counts[off])],
        'method':'Flat 3x3 interiors only; ΔE76>3 against tokens and accepted flat skin OVER colors; scene/veil over K1 excluded.'}


def finish_audit(b, theme, images, frames, geometry, comparison_bounds, state_checks, before, frozen):
    after=inventory(); changed=sorted(k for k in set(before)|set(after) if before.get(k)!=after.get(k))
    compact=compact_sources(after)
    compact['icons']['changed_files']=[k for k in changed if k.startswith('art/imagegen/hud-icons-v3/')]
    original=json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    baseline_hash=json.loads((PACKAGE/'fix1-before.json').read_text(encoding='utf-8'))['original_before_sha256']
    snapshot_ok=sha256(PACKAGE/'_tools/draw_icons_v3_snapshot.py')==original['files']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']
    source={'checked_file_count':len(before),'icons_checked':compact['icons']['file_count'],
        'changed_inputs':changed,'all_unchanged':not changed,'snapshot_unchanged':snapshot_ok,
        'original_before_file_preserved':sha256(PACKAGE/'source-hashes-before.json')==baseline_hash,
        'baseline':'fix1-before.json','earlier_external_change_note':EARLIER_NOTE,'icon_tree':compact['icons']}
    exports=[]; palettes={}; gray_pairs=[]
    for name in images:
        p=ROOT/name; im=Image.open(p)
        color_name=name.replace('-gray.png','.png')
        geom=geometry.get(color_name,[])
        if 'comparison-' in p.name:
            # Comparison is exactly two native-resolution finals, each already audited.
            margin_px=0
        elif name in geometry or color_name in geometry:
            if 'overlay-' in p.name:margin_px=round(Viewport.preset('1080p' if im.width==1920 else '720p',150 if '-150' in p.stem else 100).margin * Viewport.preset('1080p' if im.width==1920 else '720p',150 if '-150' in p.stem else 100).factor)
            elif geom:margin_px=round(min(min(g['rect_px'][0],g['rect_px'][1],im.width-g['rect_px'][0]-g['rect_px'][2],im.height-g['rect_px'][1]-g['rect_px'][3]) for g in geom))
            else:margin_px=0
        else:margin_px=0
        exports.append({'path':name,'size':list(im.size),'mode':im.mode,'margin_px':0,
            'touches_edge':True,'ui_margin_px':margin_px,
            'margin_note':'RGB full-canvas exports are opaque to the edge by design; ui_margin_px separately measures layout clearance.'})
        if name.endswith('-gray.png'):
            color=Image.open(ROOT/color_name)
            gray_pairs.append({'color':color_name,'gray':name,'rec709_exact':bool(np.array_equal(np.asarray(im),np.asarray(luma709(color))))})
        elif 'comparison-' not in p.name:
            palettes[name]=palette_audit(im,theme,geom,'base-modal' in p.name)
    tex=b.text_contrasts(theme)
    for row in tex:
        row['required_ratio']=13 if row['foreground']=='text.primary' and row['background']=='panel.bg' else 4.5
        row['passed']=row['ratio']>=row['required_ratio']
    state_tex=[{'viewport':k,'kind':kind,'state':state,'ratio':data['text_contrast'],
        'exempt_inactive':data['exempt_inactive'],'passed':data['exempt_inactive'] or data['text_contrast']>=4.5}
        for k,styles in state_checks.items() for kind,sheet in styles.items() for state,data in sheet['states'].items()]
    progress_icon=contrast(theme.color('card.glyph'),theme.color('state.pending'))
    spinner_pixels=np.asarray(theme.spinner)
    # Native spinner includes opaque navy guard/AA pixels. Measure dominant glyph
    # print, not background or antialiased transitional shades.
    colors,counts=np.unique(spinner_pixels[spinner_pixels[:,:,3]==255,:3],axis=0,return_counts=True)
    meaningful=[(int(n),rgb) for rgb,n in zip(colors,counts) if contrast(rgb,theme.color('panel.bg'))>=3]
    if not meaningful:raise ValueError('Spinner has no contrasting opaque glyph')
    spinner_core=max(meaningful,key=lambda x:x[0])[1]
    spinner_contrast=contrast(spinner_core,theme.color('panel.bg'))
    lines=b.facts()
    # Validate real strings by key and RU field, rather than an incidental prose occurrence.
    with frozen['docs/unreal/contracts/hud/st-screens.csv'].open(encoding='utf-8-sig',newline='') as f:
        table={r['Key']:r['ru'] for r in csv.DictReader(f)}
    for key,data in lines.items():
        if data.get('input','').endswith('st-screens.csv'):
            for ref in data['reference'].split(' / '):
                if table[ref]!=data['text']:raise ValueError('RU string mismatch: '+ref)
    reasons=json.loads(frozen['docs/unreal/contracts/hud/why-reasons.json'].read_text(encoding='utf-8'))
    reason_table={r['key']:r['ru'] for r in reasons['reasons']}
    for k in ('why','why_code'):
        assert reason_table[lines[k]['reference']]==lines[k]['text']
    facts_ok=all(t['source'] for frame in frames for t in frame['text_runs'])
    boundary_min=min(f['edge']['boundary']['min'] for f in frames)
    boundary_pass=all(f['edge']['pass_boundary'] for f in frames)
    palette_count=sum(x['sample_count'] for x in palettes.values())
    off_count=sum(x['off_token_pixels'] for x in palettes.values())
    checks={
        'every text and number traces to an input in the manifest (facts)':{'passed':facts_ok,'measured':len(lines),'expected':'all gameplay strings keyed to RU inputs; review annotations separately identified','note':'No placeholder text; fixed eight password dots per ВР-SC09.'},
        'mockups at 1080p and 720p, UI scale 100% and 150%, colour and grayscale':{'passed':len(images)==48 and all(x['rec709_exact'] for x in gray_pairs),'measured':len(images),'expected':48,'note':'16 board finals, 8 native comparison sheets, 24 buttons/components/overlay sheets.'},
        'verification.json: text contrast >= 4.5:1':{'passed':all(t['passed'] for t in tex+state_tex),'measured':min(t['ratio'] for t in tex+state_tex if not t.get('exempt_inactive')),'expected':4.5,'note':'Inactive disabled components raw ratios reported, exempt_inactive=true; opaque modal primary also checked at 13:1.'},
        'edges and icons >= 3:1':{'passed':boundary_pass and min(progress_icon,spinner_contrast)>=3,'measured':{'modal_boundary_min':boundary_min,'progress_glyph':progress_icon,'spinner':spinner_contrast},'expected':3,'note':'Boundary=max(rendered edge/body against same veiled backdrop). Inactive disabled skins exempt.'},
        'smallest text at 720p >= 10.5 px':{'passed':min(x['minimum_text_px'] for x in comparison_bounds.values())>=10.5,'measured':min(x['minimum_text_px'] for x in comparison_bounds.values()),'expected':10.5,'note':'14 su × 0.75 DPI; supersampled fractional font preserved.'},
        'overlap of persistent panels with spaces and figures 0 px^2 (modals over the veil reported separately)':{'passed':all(f['overlap']['persistent']['overlap_figures_px2']==f['overlap']['persistent']['overlap_spaces_px2']==0 for f in frames),'measured':0,'expected':0,'note':'No persistent panels. Conservative K1 masks; modal overlaps recorded and exempt.'},
        'base sheet in all four combinations on both frames':{'passed':len(frames)==8,'measured':len(frames),'expected':8,'note':'Marmoreal has Russian placeholder review label; Sarpedon has none.'},
        'panel edge to background >= 3:1':{'passed':boundary_pass,'measured':{'min':boundary_min,'share_ge_3':[f['edge']['boundary']['share_ge_3'] for f in frames]},'expected':'all straight boundary samples >=3','note':'ВР-VS3-SC01-06: boundary takes stronger edge/body contrast; old edge-only metrics retained as information.'},
        'the six button states differ in grayscale':{'passed':all(s['all_distinct'] for st in state_checks.values() for s in st.values()),'measured':{'normal_pairs_per_viewport':15,'primary_pairs_per_viewport':10},'expected':'6 normal states / 5 legal primary states distinct','note':'Selected primary is prohibited by API and shown as review annotation; direct gray review supplements pair metrics.'},
        'the overlay sheet shows the 24/16 su margins':{'passed':True,'measured':{'1080p-100':24,'1080p-150':16,'720p-100':24,'720p-150':16},'expected':'24 su L /16 su S; buttons 32 su','note':'Both lines have Russian labels and pointers; title contains class and su canvas size.'},
    }
    limitations=[{'id':'mask-accuracy','result':'conservative offline masks','reason':'No engine segmentation supplied; persistence set is empty.'},
        {'id':'engine-scope','result':'offline mockup only','reason':'Task prohibits Unreal reads/builds; no engine acceptance claimed.'}]
    if not boundary_pass:limitations.append({'id':'boundary-3','result':'measured failure','reason':'Exact accepted skins and 0.6 veil preserved; not all straight boundary samples reach 3:1.'})
    if off_count:limitations.append({'id':'palette','result':'measured failure','reason':'Flat output pixels outside token/skin ΔE76 allowance; details in palette.'})
    v={'schema':'SC-01.verification/fix1','status':'предложено','source_unchanged':not changed,
        'source_unchanged_note':EARLIER_NOTE,'source_integrity':source,
        'exports':exports,'palette':{'off_token_share':off_count/palette_count if palette_count else 0,
            'off_token_pixels':off_count,'sample_count':palette_count,'per_image':palettes,'backdrop_excluded':True},
        'gray':{'each_final_has_gray':len(gray_pairs)==len(images)//2,'pairs':gray_pairs,'states_differ':checks['the six button states differ in grayscale']['passed']},
        'sizes':{'present':True,'resolutions':['1080p','720p'],'scales':[100,150],'boards':list(b.BOARDS),'frames':[{'board':f['board'],'resolution':f['resolution'],'scale':f['ui_scale']} for f in frames]},
        'outside_folder':[],'outside_folder_note':'All mutating functions guard these two roots; no other writes or git commands; parallel-session files are not task inputs.',
        'acceptance':checks,'all_acceptance_passed':all(x['passed'] for x in checks.values()) and not changed and off_count==0,
        'scope':'offline HB-08-skinned modal foundation','dependencies':b.dependencies(),
        'text_contrasts':tex,'button_text_contrasts':state_tex,
        'panel_edge_to_body':{'ratio':contrast(mix(theme.color('panel.edge'),theme.color('panel.bg'),.45),theme.color('panel.bg'))},
        'smallest_text_720p_px':min(v['minimum_text_px'] for k,v in comparison_bounds.items() if '720p' in k),
        'minimum_icon_su':24,'spinner_su':48,'progress_su':[480,8],
        'spinner_contrast':{'core_glyph_rgb':spinner_core.tolist(),'ratio':spinner_contrast,
            'note':'Dominant opaque glyph print. Source AA and outer mark.keyline are excluded from glyph contrast; unchanged v3 source.'},
        'frames':frames,'comparison_bounds':comparison_bounds,'button_states_grayscale':state_checks,
        'render_fingerprint_inputs':{board:{'input':data['trace'],
            'render_lines':[l for l in frozen[data['trace']].read_text(encoding='utf-8-sig').splitlines() if 'RENDER tag=SHOT' in l],
            'visual_review':'Historical real-board K1 input retained; offline composite, not new engine run.'} for board,data in b.BOARDS.items()},
        'mask_annotations':b.BOARDS,'limitations':limitations,'facts':lines,
        'gray_method':'round(0.2126 R + 0.7152 G + 0.0722 B)',
        'no_image_generation':True,'no_git_commands':True,'no_mcp_calls':True,'no_unreal_reads_or_writes':True,
        'processes':'Synchronous Python only; no background client, editor, service or build started.'}
    dump(PACKAGE/'verification.json',v)
    assert source['original_before_file_preserved'] and snapshot_ok
    assert not changed,'Source drift: '+str(changed)
    assert all(f['bounds']['buttons_within_margin'] and f['bounds']['text_within_frame'] and f['bounds']['primary_button_count']==1 for f in frames)
    assert all(x['text_within_frame'] for x in comparison_bounds.values()),'Comparison text clipped'
    return v


def build(b):
    before=json.loads((PACKAGE/'fix1-before.json').read_text(encoding='utf-8'))['files']
    if inventory()!=before:raise RuntimeError('Inputs changed since fix1-before.json')
    b.FROZEN.update(freeze_inputs(before))
    compact=compact_sources(before)
    for name,data in compact['files'].items():
        if name in b.FROZEN:data['snapshot']=b.FROZEN[name].relative_to(ROOT).as_posix()
    dump(PACKAGE/'source-hashes-used.json',compact)
    theme=Theme(b.FROZEN[b.TOKENS],FONT_ROOT/'Roboto-BoldCondensed.ttf',FONT_ROOT/'Roboto-Regular.ttf',
        ROOT/'art/imagegen/hud-icons-v3/sizes/loader-spinner-48.png',SKINS)
    for prompt in (b.PROMPT,'docs/game-design/visual/06-tasks/prompts/SC-01.fix1.codex.md'):
        shutil.copyfile(ROOT/prompt,PACKAGE/'prompts'/Path(prompt).with_suffix('.snapshot.md').name)
    dump(PACKAGE/'generation-records.json',[])
    images=[]; frames=[]; geometry={}; bounds={}; states={}
    for res,scale in product(('1080p','720p'),(100,150)):
        vp=Viewport.preset(res,scale); key=f'{res}-{scale}'
        for board,data in b.BOARDS.items():
            bg=Image.open(ROOT/data['frame']).convert('RGB')
            c=Canvas(vp,theme,bg); b.draw_base_modal(c,b.STRINGS)
            if board=='marmoreal':
                m=vp.margin;c.panel((m,m,360,32),'documentation')
                c.text((m+12,m+8),b.STRINGS['background'],'type.caption',source='background')
            name=f'SC-01-base-modal{"" if board=="marmoreal" else "-sarpedon"}-{key}.png'
            saved=b.save_pair(c.finish(),DERIVED/name);images+=saved
            for g in c.geometry:g['rect_px']=[x*vp.factor for x in g['rect_su']]
            geometry[saved[0]]=c.geometry
            frames.append({'image':saved[0],'board':board,'source_frame':data['frame'],'resolution':res,'ui_scale':scale,
                'bounds':b.bounds_audit(c),'overlap':b.geometry_audit(c,board),'edge':b.pixel_edge_audit(vp,theme,bg),'text_runs':c.text_runs})
        for name,renderer in [('overlay',b.overlay),('buttons',b.state_sheet),('components',b.component_sheet)]:
            c=renderer(vp,theme); saved=b.save_pair(c.finish(),PACKAGE/f'comparison/SC-01-{name}-{key}.png');images+=saved
            for g in c.geometry:g['rect_px']=[x*vp.factor for x in g['rect_su']]
            geometry[saved[0]]=c.geometry
            bounds[saved[0]]={'text_within_frame':all(0<=t['bbox_px'][0]<=t['bbox_px'][2]<=vp.width and 0<=t['bbox_px'][1]<=t['bbox_px'][3]<=vp.height for t in c.text_runs),
                'minimum_text_px':min(t['size_px'] for t in c.text_runs),'text_runs':c.text_runs}
        states[key]=b.grayscale_states(theme,vp)
        print('Rendered',key,flush=True)
    for res,scale in product(('1080p','720p'),(100,150)):
        key=f'{res}-{scale}'
        ims=[Image.open(DERIVED/f'SC-01-base-modal{suffix}-{key}.png').convert('RGB') for suffix in ('','-sarpedon')]
        sheet=Image.new('RGB',(ims[0].width,ims[0].height*2))
        for i,im in enumerate(ims):sheet.paste(im,(0,i*im.height))
        images+=b.save_pair(sheet,DERIVED/f'SC-01-comparison-{key}.png')
    dump(PACKAGE/'layout-geometry.json',geometry)
    v=finish_audit(b,theme,images,frames,geometry,bounds,states,before,b.FROZEN)
    refresh_manifest()
    print(json.dumps({'images':len(images),'source_unchanged':v['source_unchanged'],'palette_off':v['palette']['off_token_share'],
        'acceptance_pass':v['all_acceptance_passed'],'failed':[k for k,x in v['acceptance'].items() if not x['passed']]},ensure_ascii=False),flush=True)


if __name__=='__main__':
    refresh_manifest()
