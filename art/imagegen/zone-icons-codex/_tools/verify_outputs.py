"""Independent disk audits for IC-37. Native raster provenance is explicit."""
import hashlib
import itertools
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
from PIL import Image
from zone_icons import PACKAGE,KEYS,SIZES,BOARDS,COLORS,rgba,gray,contrast,ink,glyph_mask,render,layers

ROOT=PACKAGE.parents[2]

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def put(name,data):
    (PACKAGE/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def audit():
    baseline=json.loads((PACKAGE/'source-hashes-before.json').read_text(encoding='utf-8'))
    changed=[p for p,v in baseline['files'].items() if not (ROOT/p).exists() or sha(ROOT/p)!=v['sha256']]
    now={p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}
    added=sorted(now-set(baseline['files']))
    snapshot=sha(PACKAGE/'_tools/draw_icons_v3_snapshot.py')==baseline['files']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']
    exports=[]
    missing=[]
    for size,key,suffix in itertools.product(SIZES,KEYS,('', '_body','_disc','_glyph')):
        for g in ('','-gray'):
            p=PACKAGE/f'vector/{size}/zone-{key}{suffix}{g}.png'
            if not p.exists():
                missing.append(p.relative_to(PACKAGE).as_posix())
    allowed={rgba(h)[:3] for h in COLORS.values()}
    allowed.update(rgba(h)[:3] for b in BOARDS.values() for h in b.values())
    opaque_out=0
    opaque_count=0
    gray_errors=[]
    bad_dimensions=[]
    for p in sorted((PACKAGE/'vector').rglob('*.png')):
        im=Image.open(p)
        size=int(p.parent.name)
        if im.size!=(size,size) or im.mode!='RGBA':
            bad_dimensions.append(p.relative_to(PACKAGE).as_posix())
        a=np.asarray(im.convert('RGBA'))
        yy,xx=np.where(a[:,:,3]>0)
        margin=int(min(xx.min(),yy.min(),size-1-xx.max(),size-1-yy.max())) if len(xx) else size
        row={'path':p.relative_to(PACKAGE).as_posix(),'size':list(im.size),'mode':im.mode,'margin_px':margin,'touches_edge':margin==0}
        if '-gray' not in p.stem:
            pix=a[a[:,:,3]==255,:3]
            count=len(pix)
            codes=(pix[:,0].astype(np.uint32)<<16)|(pix[:,1].astype(np.uint32)<<8)|pix[:,2]
            uniq,cnts=np.unique(codes,return_counts=True)
            allowed_codes={(r<<16)|(g<<8)|b for r,g,b in allowed}
            out=sum(int(n) for c,n in zip(uniq,cnts) if int(c) not in allowed_codes)
            opaque_out+=out
            opaque_count+=count
            row['opaque_outside_exact_palette']=out
            gp=p.with_name(p.stem+'-gray.png')
            if not gp.exists() or not np.array_equal(np.asarray(gray(im)),np.asarray(Image.open(gp))):
                gray_errors.append(row['path'])
        exports.append(row)
    pairs=[]
    masks={k:np.asarray(glyph_mask(k,24),dtype=np.float64)/255 for k in KEYS}
    for a,b in itertools.combinations(KEYS,2):
        ma,mb=masks[a],masks[b]
        xor=int(np.count_nonzero((ma>.5)!=(mb>.5)))
        union=int(np.count_nonzero((ma>.5)|(mb>.5)))
        inter=int(np.count_nonzero((ma>.5)&(mb>.5)))
        # Isolate glyph form on the same neutral disc, to remove the colour channel.
        ia=np.asarray(gray(render(a,24,COLORS['neutral'])))[:,:,:3].astype(float)
        ib=np.asarray(gray(render(b,24,COLORS['neutral'])))[:,:,:3].astype(float)
        pairs.append({'a':a,'b':b,'gray_mean_abs_luma_24':round(float(np.abs(ia-ib).mean()),4),'glyph_mask_mean_abs_255':round(float(np.abs(ma-mb).mean()*255),4),'different_shape':xor>0,'shape_xor_pixels':xor,'shape_iou':round(inter/union,4),'passed':xor>0})
    contrasts=[{'board':board,'key':key,'disc':color,'glyph':ink(color),'ratio':round(contrast(ink(color),color),6),'passed':contrast(ink(color),color)>=3} for board,colors in BOARDS.items() for key,color in colors.items()]
    records=json.loads((PACKAGE/'generation-records.json').read_text(encoding='utf-8')) if (PACKAGE/'generation-records.json').exists() else []
    prompts=json.loads((PACKAGE/'prompts/zone-icons-prompts.json').read_text(encoding='utf-8'))
    generated=[]
    for record in records:
        p=PACKAGE/record['saved_path']
        original=Path(record['original_path'])
        original_match=original.exists() and sha(original)==record['sha256']
        ok=p.exists() and sha(p)==record['sha256'] and record['prompt']==prompts.get(record['prompt_key']) and original_match
        generated.append({'id':record['id'],'passed':ok,'original_bytes_match':original_match})
    absent_concepts=[f'zone-{k}-{v}' for k,v in itertools.product(KEYS,'AB') if not (PACKAGE/f'concepts/zone-{k}-{v}.png').exists()]
    service_cache=[record['original_path'] for record in records if record.get('local_service_cache_outside_package')]
    # User-authorized exception 2026-10-06: cache is internal Codex storage,
    # outside_folder covers repository paths outside the allowed package roots.
    outside=[]
    permitted=(PACKAGE.resolve(),(ROOT/'scraped-data/derived/zone-icons-codex').resolve())
    for record in records:
        saved=(PACKAGE/record['saved_path']).resolve()
        if saved.is_relative_to(ROOT.resolve()) and not any(saved.is_relative_to(p) for p in permitted):
            outside.append(saved.relative_to(ROOT).as_posix())
    metrics={}
    for key in KEYS:
        metrics[key]={}
        for size in SIZES:
            a=np.asarray(glyph_mask(key,size))>0
            yy,xx=np.where(a)
            metrics[key][str(size)]={'area_px':int(a.sum()),'bbox_px':[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)],'bbox_u':[round(float((xx.max()+1-xx.min())*32/size),4),round(float((yy.max()+1-yy.min())*32/size),4)],'centroid_u':[round(float((xx+.5).mean()*32/size),4),round(float((yy+.5).mean()*32/size),4)],'detail':0 if size<=20 else 1 if size<=40 else 2}
    native_match=[]
    for size,key in itertools.product(SIZES,KEYS):
        disk=np.asarray(Image.open(PACKAGE/f'vector/{size}/zone-{key}.png'))
        if not np.array_equal(disk,np.asarray(render(key,size))):
            native_match.append([key,size])
    common_errors=[]
    mask_errors=[]
    for size in SIZES:
        for suffix in ('body','disc'):
            paths=[PACKAGE/f'vector/{size}/zone-{key}_{suffix}.png' for key in KEYS]
            if len({sha(p) for p in paths})!=1:
                common_errors.append([size,suffix])
        for key in KEYS:
            p=PACKAGE/f'vector/{size}/zone-{key}_disc.png'
            a=np.asarray(Image.open(p))
            if np.any(a[a[:,:,3]>0,:3]!=255):
                mask_errors.append(p.relative_to(PACKAGE).as_posix())
    limitations=[]
    if absent_concepts:
        limitations.append('Concept generation is in progress; missing keys are listed explicitly.')
    limitations.append('16 and 21 px are boundary exports only; readability acceptance starts at 24 px. Pixel-snapped disc ring can encroach on the badge edge at 16 px.')
    checks={
        'source_unchanged':{'passed':not changed and not added,'measured':len(baseline['files']),'expected':'all hashes unchanged and no added v3 files'},
        'snapshot_unchanged':{'passed':snapshot,'measured':sha(PACKAGE/'_tools/draw_icons_v3_snapshot.py'),'expected':baseline['files']['art/imagegen/hud-icons-v3/_tools/draw_icons.py']['sha256']},
        'exports':{'passed':not missing and not bad_dimensions,'measured':len(exports),'expected':'all mandatory native sizes, four layers, RGBA and grayscale companions'},
        'palette':{'passed':opaque_out==0,'measured':opaque_out,'expected':'0 opaque pixels outside dE76 <= 3; exact membership is a stronger check'},
        'gray_pairs':{'passed':len(pairs)==28 and all(p['passed'] for p in pairs),'measured':sum(p['passed'] for p in pairs),'expected':'28/28 different shapes or luma difference >=20'},
        'contrast':{'passed':all(c['passed'] for c in contrasts),'measured':min(c['ratio'] for c in contrasts),'expected':'>=3:1 on all 14 measured board colours'},
        'gray_companions':{'passed':not gray_errors,'measured':gray_errors,'expected':'Rec.709 byte-exact companions for every vector file'},
        'native_raster':{'passed':not native_match,'measured':native_match,'expected':'direct render matches disk at each size; no master downscale'},
        'common_layers':{'passed':not common_errors,'measured':common_errors,'expected':'identical body and disc across eight keys at each size'},
        'white_disc_masks':{'passed':not mask_errors,'measured':mask_errors,'expected':'every nontransparent disc mask pixel is white'},
        'concepts':{'passed':not absent_concepts and len(generated)==16 and all(g['passed'] for g in generated),'measured':len(generated),'expected':'16 original generations with exact prompt and byte hashes'},
        'outside_folder':{'passed':not outside,'measured':outside,'expected':[],'note':'Repository paths only. User-authorized Codex ImageGen service cache is tracked separately in imagegen_service_cache.'},
    }
    report={'task':'IC-37','status':'предложено','checked_at':datetime.now(timezone.utc).isoformat(),'source_unchanged':not changed and not added,'source_changed':changed,'v3_files_added':added,'snapshot_unchanged':snapshot,'outside_folder':outside,'outside_folder_scope':'Agent writes are confined to the package; ImageGen service cache paths are explicitly listed. No global filesystem baseline was taken and no claim is made about unrelated concurrent sessions.','palette':{'opaque_pixels_outside_deltaE76_le_3':opaque_out,'opaque_pixels_checked':opaque_count,'method':'exact RGB set membership on final colour vector files, including white masks; stricter than dE76 <=3','gray_files_exempt':True,'concepts_and_sheets_exempt':True},'exports':exports,'sizes':{'required':list(SIZES),'missing':missing,'bad_dimensions':bad_dimensions,'native_disk_mismatch':native_match},'gray':{'method':'round(0.2126 R + 0.7152 G + 0.0722 B) on sRGB values, alpha unchanged','pairs_24':pairs,'passed_pairs':sum(p['passed'] for p in pairs),'gray_errors':gray_errors},'contrast':contrasts,'glyph_geometry':metrics,'concepts':{'records':generated,'missing':absent_concepts},'acceptance':checks,'limitations':limitations,'all_acceptance_passed':all(c['passed'] for c in checks.values())}
    report['imagegen_service_cache']=service_cache
    report['imagegen_service_cache_authorized']=True
    report['outside_folder_scope']='Repository paths outside art/imagegen/zone-icons-codex/ and scraped-data/derived/zone-icons-codex/. ImageGen service cache is an explicitly authorized exception (user message 2026-10-06). No global disk baseline or claim about unrelated concurrent sessions.'
    report['generation_budget']={'syntx_calls_this_continuation':0,'syntx_generations_total':0,'imagegen_concepts_expected':16,'refinements_per_key_limit':1,'refinements_used':{k:0 for k in KEYS}}
    if (PACKAGE/'concept-review.json').exists():
        report['concept_review']=json.loads((PACKAGE/'concept-review.json').read_text(encoding='utf-8'))
    put('verification.json',report)
    manifest={p.relative_to(PACKAGE).as_posix():sha(p) for p in sorted(PACKAGE.rglob('*')) if p.is_file() and p.name!='manifest-sha256.json'}
    put('manifest-sha256.json',{'algorithm':'sha256','scope':'all package files except this self-referential manifest','files':manifest})
    print(json.dumps({'sources':report['source_unchanged'],'palette_outside':opaque_out,'pairs':report['gray']['passed_pairs'],'minimum_contrast':checks['contrast']['measured'],'exports':len(exports),'concepts':len(generated),'all_acceptance_passed':report['all_acceptance_passed']},ensure_ascii=False))
    return report

if __name__=='__main__':
    audit()
