"""Read-only corrective-run proofs; the original fix1-before.json is immutable."""
import hashlib, math
from collections import defaultdict
import numpy as np
from PIL import Image, ImageDraw
import build_mockups as b


def english_probes():
    """Native EN caption measurements on both L canvases, without extra exports."""
    fits=[];texts=[]
    for board in b.BG:
        for w,h,ui,s in b.CONFIGS:
            if ui!=100:continue
            for state in ('own-2','hover'):
                ident=f'HB-42-{board}-caption-probe-{state}-en-{w}x{h}-{ui}'
                c=b.Canvas(board,w,h,s,ident);c.rules=b.state_rules(state)
                cells=b.draw_buttons(c,'L',b.geom(board,w,h,ui)[1]['ACTIONS'],c.rules,'en')
                fits.extend(dict(cell['caption_fit'],measurement_only=True,measurement_source='Native in-memory caption layer, exact canvas pixels; no extra final exported') for cell in cells)
                texts.append({'id':ident,'board':board,'resolution':[w,h],'su_to_px':s,'purpose':'EN rest / hover caption geometry on each class L canvas','texts':c.texts})
    return fits,texts


def audit(v):
    before=b.load(b.PKG/'fix1-before.json')
    ss=[]
    for path,old in before['class_s_files'].items():
        p=b.ROOT/path
        with Image.open(p) as im:
            pixel_sha=hashlib.sha256(im.convert('RGBA').tobytes()).hexdigest()
            equal=pixel_sha==old['pixel_sha256'] and list(im.size)==old['size']
        ss.append({'path':path,'before_sha256':old['sha256'],'after_sha256':b.sha(p),'pixel_identical':equal,'different_pixels':0 if equal else None,'before_pixel_sha256':old['pixel_sha256'],'after_pixel_sha256':pixel_sha})
    # A matching whole-image pixel digest proves zero changed pixels without a rescale.
    baseline_errors=[];caption_pixel_errors=[];groups=defaultdict(list);audited_caption_layers=0
    fits={(c['id'],c['action']):c for c in v['caption_fit']}
    for g in v['geometry']:
        if g['class']!='L':continue
        s=g['su_to_px'];baseline=math.floor((g['ACTIONS'][1]+67)*s)
        with Image.open(b.OUT/(g['id']+'.png')) as im:
            frame=np.asarray(im.convert('RGB'))
        for cell in g['cells']:
            audited_caption_layers+=1
            a=cell['action'];fit=fits[g['id'],a]
            tx=next(t for t in v['contrast']['text'] if t['id']==g['id'] and t['string_key']=='hud.action.'+a)
            if fit['baseline_px']!=baseline:baseline_errors.append({'id':g['id'],'action':a,'expected':baseline,'actual':fit['baseline_px']})
            f=b.font(14*s);bb=f.getbbox(tx['text'],anchor='ls')
            local=Image.new('L',(bb[2]-bb[0]+8,bb[3]-bb[1]+8))
            ImageDraw.Draw(local).text((4-bb[0],4-bb[1]),tx['text'],font=f,fill=255,anchor='ls')
            actual=local.getbbox();r=cell['cell_su']
            x=round((r[0]+r[2]/2)*s-(actual[0]+actual[2])/2)
            y=baseline+bb[1]-4
            want=[x+actual[0],y+actual[1],x+actual[2],y+actual[3]]
            solid=np.asarray(local)==255;region=frame[y:y+local.height,x:x+local.width]
            bad=int(np.count_nonzero(np.any(region[solid]!=np.array(b.rgb(tx['token'])),axis=1)))
            if want!=fit['ink_bbox_px'] or bad:caption_pixel_errors.append({'id':g['id'],'action':a,'expected_bbox':want,'reported_bbox':fit['ink_bbox_px'],'incorrect_solid_text_pixels':bad})
            groups[g['id']].append(fit['baseline_px'])
    old_groups=defaultdict(list)
    for t in before['caption_text']:old_groups[t['id']].append(t['baseline_px'])
    cf=v['caption_fit']
    return {'task':'HB-42 fix1','decisions':['ВР-VS2-HB42-'+str(i) for i in range(12,19)],'prompt':'docs/game-design/visual/06-tasks/prompts/HB-42.fix1.codex.md','prompt_sha256':b.sha(b.ROOT/'docs/game-design/visual/06-tasks/prompts/HB-42.fix1.codex.md'),'before_snapshot_sha256':b.sha(b.PKG/'fix1-before.json'),'source_inventory_preserved':b.sha(b.PKG/'source-hashes-before.json')==before['source_hashes_before_sha256'],'class_s_unchanged':{'passed':all(x['pixel_identical'] for x in ss),'files':len(ss),'different_pixels':0 if all(x['pixel_identical'] for x in ss) else None,'method':'RGBA pixel SHA-256 and dimensions before / after; identical digests prove 0 differing pixels','per_file':ss},'caption_pixel_audit':{'passed':not baseline_errors and not caption_pixel_errors,'L_rows':len(groups),'caption_layers':audited_caption_layers,'additional_native_EN_measurements':sum(c.get('measurement_only',False) for c in cf),'baseline_errors':baseline_errors,'pixel_errors':caption_pixel_errors,'method':'Independent font masks at common floor baseline; alpha>0 bounding boxes and every solid caption pixel checked against saved final'},'before_after':{'cell_widths_su':{'before':[80]*4,'after':[78,78,78,86]},'caption_baseline_span_px':{'before':max(max(g)-min(g) for g in old_groups.values()),'after':max(max(g)-min(g) for g in groups.values())},'caption_min_side_free_su':{'before':min(min(x['left_free_su'],x['right_free_su']) for x in before['caption_fit']),'after':min(min(x['left_free_su'],x['right_free_su']) for x in cf)},'caption_side_failures':{'before':sum(not x['passed'] for x in before['caption_fit']),'after':sum(not x['checks']['side'] for x in cf)},'caption_bottom_min_su':min(x['bottom_clearance_su'] for x in cf),'remaining_caption_failures':[c for c in cf if not c['passed']],'acceptance_failed_before':list(before['failed_acceptance']),'acceptance_failed_after':[k for k,a in v['acceptance'].items() if not a['passed']]}}
