"""Independent checks of exported PNG bytes and 9-slice behavior."""
import sys,itertools
sys.dont_write_bytecode=True
from build_kit import *
ASSETS.update(json.loads((KIT/'assets.json').read_text('utf-8')))

def lum(c):
    q=np.array(rgb(c))/255
    q=np.where(q<=.04045,q/12.92,((q+.055)/1.055)**2.4)
    return float(q@np.array([.2126,.7152,.0722]))
def contrast(a,b):
    x,y=sorted([lum(a),lum(b)]);return (y+.05)/(x+.05)

def stretch_sheet(name):
    d=ASSETS[name]
    ws=[144,240,336];hs=[80,112,160]
    # For panels the nine requested width/height combinations are all independent.
    page=Image.new('RGB',(1700,510),NAVY);draw=ImageDraw.Draw(page)
    for side,bg in enumerate([NAVY,'#E2DACD']):
        dx=side*850;draw.rectangle((dx,0,dx+849,509),fill=bg)
        color=LIGHT if side==0 else NAVY;text(page,(dx+12,8),name+' / 3 widths x 3 heights / x1',20,color)
        y=48
        for h in hs:
            x=dx+12
            for w in ws:
                q=render(name,(w,h));page.paste(q,(x,y),q);text(page,(x+8,y+8),f'{w} x {h}',16,LIGHT)
                x+=w+16
            y+=h+22
    path=PRE/'stretch'/(name+'.png');save(page,path)

def main():
    results=[];contrasts=[];failure=[];stretch_cases=0;colour_conflicts=[];body_samples=[]
    v1=json.loads((ROOT/'art/imagegen/hud-skins-v1-codex/manifest.json').read_text('utf-8'))
    navy_new={'T_Hud_'+n for n in ['StatusBanner','TurnPlate','HpPlate','PileFrame','ActionPlate','HandTray','FighterPlate','FighterPlate_Enemy']}
    for n,d in ASSETS.items():
        if d['body_color']:
            cr=contrast(d['text_color'],d['body_color']);contrasts.append({'name':n,'text':d['text_color'],'body':d['body_color'],'ratio':round(cr,5)})
            if cr<4.5:colour_conflicts.append({'asset':n,'text':d['text_color'],'body':d['body_color'],'ratio':round(cr,5),'reason':'Fixed game text and mandatory v1 body cannot meet 4.5:1 together.'})
        for folder,v in d['files'].items():
            p=ART/v['path'];im=Image.open(p);a=np.array(im);sc=v['scale'];w,h=im.size
            assert im.mode=='RGBA' and list(im.size)==v['size_px'] and sha(p)==v['sha256']
            al=a[:,:,3];hidden=int(np.any(a[al==0,:3]!=0,axis=1).sum())
            green=int(((a[:,:,1].astype(int)>a[:,:,0].astype(int)+32)&(a[:,:,1].astype(int)>a[:,:,2].astype(int)+32)&(al>0)).sum())
            rec={'file':v['path'],'size':list(im.size),'scale':sc,'transparent_rgb_nonzero':hidden,'green_fringe_pixels':green,'center_alpha':int(al[h//2,w//2]),'slice_checks':[]}
            if d['body_color']:
                # Measure actual exported straight RGBA, not metadata. The central
                # +/-10 percent of width/height is required to be flat text body.
                x0,x1=round(w*.4),round(w*.6);y0,y1=round(h*.4),round(h*.6)
                if n.startswith('T_Skin_'):
                    sty=v1['skins']['vector/x1/'+n+'.png']['style']
                    expected_body=v1['tokens'][sty['body']];expected_opacity=sty['body_opacity'];contract_source='hud-skins-v1-codex/manifest.json'
                elif n in navy_new:
                    expected_body=NAVY;expected_opacity=.92;contract_source='B2 hard contract: new navy text plates'
                else:expected_body=d['body_color'];expected_opacity=d['body_opacity'];contract_source='B2 remaining asset contract'
                patch=a[y0:y1,x0:x1];expected=np.array([*rgb(expected_body),round(expected_opacity*255)])
                if d['body_color']!=expected_body or d['body_opacity']!=expected_opacity:failure.append(n+': metadata differs from hard contract')
                max_error=np.abs(patch.astype(int)-expected).max(axis=(0,1)).tolist()
                if max(max_error)>1:failure.append(v['path']+': body colour/opacity differs')
                center=a[h//2,w//2];actual='#'+''.join(f'{z:02X}' for z in center[:3]);op=float(center[3])/255
                text_colours=[d['text_color']]
                if d['text_color']==LIGHT:text_colours.append('#B9B2A6')
                pairs=[]
                for tc in text_colours:
                    composites=[]
                    for bg in ['#000000',NAVY,'#E2DACD','#FFFFFF']:
                        cc=np.round(center[:3]*op+np.array(rgb(bg))*(1-op)).astype(int)
                        hx='#'+''.join(f'{z:02X}' for z in cc)
                        composites.append({'backdrop':bg,'composited_body':hx,'ratio':round(contrast(tc,hx),5)})
                    pairs.append({'game_text_colour':tc,'uncomposited_ratio':round(contrast(tc,actual),5),'minimum_composited_ratio':min(x['ratio'] for x in composites),'passes_4_5':all(x['ratio']>=4.5 for x in composites),'backdrops':composites})
                body_samples.append({'file':v['path'],'name':n,'scale':sc,'centre_rgba':center.tolist(),'measured_body_colour':actual,'measured_opacity':round(op,6),
                    'expected_body_colour':expected_body,'expected_opacity':expected_opacity,'contract_source':contract_source,'sampling_region_px':[x0,y0,x1,y1],
                    'sampling_region':'centre +/-10% width and height','maximum_channel_error':max_error,'colour_and_opacity_pass':max(max_error)<=1,'text_contrasts':pairs})
            if hidden or green:failure.append(v['path']+': alpha/green')
            l,t,r,b=[v['slice_px'][k] for k in ['left','top','right','bottom']]
            if d['stretch'] in ['nine_slice','horizontal']:
                checks=[]
                for region,axis in [(a[:t,l:w-r],1),(a[h-b:,l:w-r],1)]:
                    if region.size:checks.append(int(np.max(np.ptp(region.astype(int),axis=axis))))
                if d['stretch']=='nine_slice':
                    for region in [a[t:h-b,:l],a[t:h-b,w-r:]]:
                        if region.size:checks.append(int(np.max(np.ptp(region.astype(int),axis=0))))
                rec['edge_axis_max_delta']=max(checks,default=0)
                if rec['edge_axis_max_delta']!=0:failure.append(v['path']+': edge axis not uniform')
                # Validate the actual stretched exports: corners must be byte-identical.
                for tw,th in itertools.product([max(w,l+r+12*sc),max(w,l+r+60*sc),max(w,l+r+180*sc)],
                                              [max(h,t+b+8*sc),max(h,t+b+36*sc),max(h,t+b+72*sc)]):
                    q=np.array(nine(im,(tw,th),(l,t,r,b)))
                    for x,y,sx,sy,cw,ch in [(0,0,0,0,l,t),(tw-r,0,w-r,0,r,t),(0,th-b,0,h-b,l,b),(tw-r,th-b,w-r,h-b,r,b)]:
                        assert np.array_equal(q[y:y+ch,x:x+cw],a[sy:sy+ch,sx:sx+cw]),(n,'corner changed')
                    stretch_cases+=1
                rec['corner_preservation_9_sizes']=True
            if d.get('focus_overlay'):
                # Empty full body (not only center pixel).
                rec['focus_body_clear']=bool((al[t:h-b,l:w-r]==0).all())
                if not rec['focus_body_clear']:failure.append(v['path']+': focus fill')
            if 'insert_rect_su' in d:
                x,y,iw,ih=[round(z*sc) for z in d['insert_rect_su']]
                rec['insert_all_clear']=bool((al[y:y+ih,x:x+iw]==0).all())
                if not rec['insert_all_clear']:failure.append(v['path']+': insert fill')
            if 'insert_diameter_su' in d:
                yy,xx=np.ogrid[:h,:w];rr=d['insert_diameter_su']*sc/2
                mask=(xx-w/2)**2+(yy-h/2)**2<(rr-sc*.75)**2
                rec['insert_circle_clear']=bool((al[mask]==0).all())
                if not rec['insert_circle_clear']:failure.append(v['path']+': circle fill')
            if d['stretch']=='tile_x':
                rec['tile_boundary_max_delta']=int(np.abs(a[:,0].astype(int)-a[:,-1].astype(int)).max())
                # Exact at each scale, not merely mathematically periodic in the master.
                if rec['tile_boundary_max_delta']>1:failure.append(v['path']+': tile seam')
            results.append(rec)
    for n in ['T_Skin_Panel','T_Skin_Modal']:stretch_sheet(n)
    old=json.loads((KIT/'stage-a-baseline.json').read_text('utf-8'));immutable=[]
    for p,h in old.items():
        if Path(p).name in ['README.md','prompts.md','generation-records.json']:continue
        if Path(p).name=='verification.json':
            prior=json.loads(Path(p).read_text('utf-8'));prior.pop('stage_b2',None)
            original=json.dumps(prior,ensure_ascii=False,indent=2).replace('\n','\r\n').encode('utf-8')
            preserved=hashlib.sha256(original).hexdigest()==h
            if preserved:(ART/'stage-a-verification.json').write_bytes(original)
            immutable.append({'path':p,'unchanged':preserved,'scope':'Original A fields reconstructed byte-for-byte, excluding the requested new stage_b2 report; archived in stage-a-verification.json.'})
        else:immutable.append({'path':p,'unchanged':sha(Path(p))==h})
    if not all(v['unchanged'] for v in immutable):failure.append('stage A changed')
    oldb=json.loads((ART/'stage-b2-baseline.json').read_text('utf-8'))
    b1_ok=all(sha(ART/'kit-b1'/rel)==h for rel,h in oldb['kit_b1_files'].items())
    if not b1_ok:failure.append('B1 backup changed')
    report={'stage':'B2','status':'technical_pass_with_fixed_colour_contrast_failures' if not failure else 'fail','all_requirements_pass':not failure and not colour_conflicts,
            'technical_status':'pass' if not failure else 'fail','failures':failure,'fixed_colour_contrast_conflicts':colour_conflicts,'body_measurements':body_samples,
            'kit_b1_hashes_preserved':b1_ok,'asset_count':len(ASSETS),'png_exports':len(results),'contrast_min':min(v['ratio'] for v in contrasts),
            'contrasts':contrasts,'files':results,'stretch_corner_cases':stretch_cases,'immutable_stage_a':immutable,
            'visual_review':'See stage-b2-visual-review.json; this file only records machine checks.',
            'limitations':['No Unreal runtime import in this asset-only task.','Exact v1 colours take priority; contrast failures are recorded, not waived.','Secondary light text is conservatively checked for every light-text substrate, including glyph/track skins without labels.','SliderThumb is a control without text; its dark-colour pair is an informational sample.']}
    write_json(ART/'stage-b2-verification.json',report)
    current=json.loads((ART/'verification.json').read_text('utf-8'));current['stage_b2']=report
    write_json(ART/'verification.json',current)
    print(json.dumps({k:report[k] for k in ['status','technical_status','failures','fixed_colour_contrast_conflicts','asset_count','png_exports','contrast_min','stretch_corner_cases']}))
    if failure:raise SystemExit(1)
    if colour_conflicts:raise SystemExit(2)
if __name__=='__main__':main()
