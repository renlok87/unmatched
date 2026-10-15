"""B2: cut generated ornament masters, keep live-game body colours immutable."""
import sys
sys.dont_write_bytecode = True
import build_kit as b
from build_kit import *

OLD = json.loads((ART/'kit-b1/assets.json').read_text('utf-8'))
V1 = json.loads((ROOT/'art/imagegen/hud-skins-v1-codex/manifest.json').read_text('utf-8'))

@lru_cache(maxsize=None)
def raw(id):
    return Image.open(next((KIT/'source-masters').glob(id+'-*.png'))).convert('RGBA')

def rgba(c,opacity=1): return (*rgb(c),round(opacity*255))

def frame(size,margin,body=NAVY,opacity=.92,state='normal',hole=False,source_id='B201'):
    w,h=[round(v*S) for v in size]; c=round(margin*S)
    src=raw(source_id)
    if source_id=='B205':
        src=src.crop((122,124,1134,1114))
        cut=230
    else:
        src=src.crop((46,60,1208,1182))
        cut=435 if margin>=20 else 300
    sw,sh=src.size
    # Each of the four corners keeps its own highlights, never mirror the lighting.
    corners=[src.crop(box).resize((c,c),Image.Resampling.LANCZOS) for box in
             [(0,0,cut,cut),(sw-cut,0,sw,cut),(0,sh-cut,cut,sh),(sw-cut,sh-cut,sw,sh)]]
    top=src.crop((sw//2,0,sw//2+1,cut)).resize((1,c),Image.Resampling.LANCZOS)
    bot=src.crop((sw//2,sh-cut,sw//2+1,sh)).resize((1,c),Image.Resampling.LANCZOS)
    left=src.crop((0,sh//2,cut,sh//2+1)).resize((c,1),Image.Resampling.LANCZOS)
    right=src.crop((sw-cut,sh//2,sw,sh//2+1)).resize((c,1),Image.Resampling.LANCZOS)
    ornament=Image.new('RGBA',(w,h))
    for i,(x,y) in enumerate([(0,0),(w-c,0),(0,h-c),(w-c,h-c)]):
        q=np.array(corners[i],dtype=float); blend=max(4,c//6)
        tp=np.array(top if i<2 else bot,dtype=float)[:,0]
        lp=np.array(left if i%2==0 else right,dtype=float)[0]
        for k in range(blend):
            f=(k+1)/blend;xx=c-blend+k if i%2==0 else blend-1-k; yy=c-blend+k if i<2 else blend-1-k
            q[:,xx]=q[:,xx]*(1-f)+tp*f
            q[yy,:]=q[yy,:]*(1-f)+lp*f
        ornament.paste(Image.fromarray(q.round().astype('uint8')),(x,y))
    ornament.paste(top.resize((w-2*c,c)),(c,0));ornament.paste(bot.resize((w-2*c,c)),(c,h-c))
    ornament.paste(left.resize((c,h-2*c)),(0,c));ornament.paste(right.resize((c,h-2*c)),(w-c,c))
    ornament=tint(ornament,state)
    out=Image.new('RGBA',(w,h))
    if not hole:
        ImageDraw.Draw(out).rounded_rectangle((S,S,w-S-1,h-S-1),radius=max(S,round(c*.17)),fill=rgba(body,opacity))
    out=Image.alpha_composite(out,ornament)
    return stabilize(out,(c,c,c,c),None)

def export(name,im,margins,stretch='nine_slice',body=None,opacity=.92,tc=LIGHT,**extra):
    if isinstance(margins,(int,float)):margins=[margins]*4
    # emit without its B1 opaque-body override, then enforce the runtime contract.
    emit(name,im,margins,stretch,None,tc,**extra)
    d=ASSETS[name];d['body_color']=body;d['body_opacity']=opacity if body else None
    d['text_safe_insets_su']=margins if body else None
    for folder,v in d['files'].items():
        p=ART/v['path'];q=Image.open(p).convert('RGBA');a=np.array(q);sc=v['scale']
        l,t,r,bt=[round(z*sc) for z in margins]
        if body:
            flat=np.all(a[:,:,:3]==np.array(rgb(body)),axis=2)&(a[:,:,3]>0)
            a[:,:,3][flat]=round(opacity*255)
            a[t:q.height-bt,l:q.width-r]=rgba(body,opacity)
            q=Image.fromarray(a)
        if stretch in ['nine_slice','horizontal']:
            q=stabilize(q,(l,t,r,bt),None,horizontal=stretch=='horizontal')
        # Gold/teal antialiasing can create a few green intermediate texels.
        # No ornament uses green; remove that spill without changing teal bodies.
        a=np.array(q);m=np.maximum(a[:,:,0],a[:,:,2]).astype(int)
        spill=(a[:,:,1].astype(int)>m+32)&(a[:,:,3]>0)
        a[:,:,1][spill]=(m[spill]+16).astype('uint8');q=Image.fromarray(a)
        save(q,p);v['sha256']=sha(p)

def cartouche2(size,margins,body=NAVY,opacity=.92):
    # B203 is 2172x724; normalize before the measured 2048-wide cut. Cropping
    # directly at 2048 would remove the right-hand acanthus spray.
    src=raw('B203').resize((2048,683),Image.Resampling.LANCZOS).crop((0,80,2048,582));sw,sh=src.size
    w,h=[z*S for z in size];l,t,r,bt=[z*S for z in margins];end=310
    out=Image.new('RGBA',(w,h));ImageDraw.Draw(out).rectangle((l//2,round(h*.16),w-r//2,round(h*.85)),fill=rgba(body,opacity))
    ornament=Image.new('RGBA',(w,h))
    ornament.paste(src.crop((0,0,end,sh)).resize((l,h),Image.Resampling.LANCZOS),(0,0))
    ornament.paste(src.crop((sw-end,0,sw,sh)).resize((r,h),Image.Resampling.LANCZOS),(w-r,0))
    profile=src.crop((1024,0,1025,sh)).resize((1,h),Image.Resampling.LANCZOS)
    ornament.paste(profile.resize((w-l-r,h)),(l,0))
    # Fixed ends blend into the uniform horizontal rails at the cut.
    a=np.array(ornament)
    for k in range(2*S):
        f=(k+1)/(2*S)
        for x in [l-2*S+k,w-r+2*S-1-k]:a[:,x]=(a[:,x]*(1-f)+np.array(profile)[:,0]*f).round()
    return stabilize(Image.alpha_composite(out,Image.fromarray(a)),(l,t,r,bt),None,horizontal=True)

def round_master(id,nominal,pad,insert,state='normal'):
    src=raw(id)
    # Keep the circle centred; the portrait laurel ends below the nominal ring.
    if id=='B202':box=(16,10,1238,1232)
    else:box=(4,4,1248,1248)
    q=src.crop(box).resize(((nominal+2*pad)*S,)*2,Image.Resampling.LANCZOS)
    q=tint(q,state)
    if state in ['hover','active']:
        alpha=q.getchannel('A').filter(ImageFilter.GaussianBlur(S*.65))
        g=Image.new('RGBA',q.size,'#FFC85D');g.putalpha(alpha.point(lambda a:round(a*.55)))
        q=Image.alpha_composite(g,q)
    # No material under the portrait/v3 disc, including antialiasing and glow.
    a=np.array(q);yy,xx=np.ogrid[:q.height,:q.width];rr=insert*S/2
    dist=np.sqrt((xx-q.width/2)**2+(yy-q.height/2)**2)
    a[:,:,3]=np.minimum(a[:,:,3],np.clip((dist-rr)*255,0,255).astype('uint8'))
    return Image.fromarray(a)

def main():
    ASSETS.clear()
    for n in V1['names']:
        old=V1['skins']['vector/x1/T_Skin_'+n+'.png'];sty=old['style']
        body=V1['tokens'][sty['body']];opacity=sty['body_opacity'];tc=NAVY if n.startswith('BtnPrimary_') else LIGHT
        if n=='SliderThumb':tc=NAVY
        margin=8;state=n.split('_')[-1].lower()
        if n in ['Panel','Modal']:margin=28
        elif n=='PanelInset':margin=12
        elif n in ['Toast','ToastWarning']:margin=24
        elif n in ['Capsule','Tag','Chip']:margin=6
        elif n=='KeyChip':margin=7
        elif n in ['ProgressTrack','ProgressFill','SliderTrack']:margin=2
        elif n=='SliderThumb':margin=4
        elif n.startswith('Check_'):margin=4
        elif n.startswith('Input_'):margin=7
        focus=n.endswith('_Focus')
        if focus:margin+=5
        content=old['content_su'];size=[content[0]+2*margin,content[1]+2*margin]
        source_id='B205' if n=='KeyChip' else 'B201'
        q=frame(size,margin,body,opacity,state if state in ['hover','pressed','disabled'] else 'normal',source_id=source_id)
        if focus:
            d=ImageDraw.Draw(q);d.rounded_rectangle((S,S,q.width-S-1,q.height-S-1),radius=5*S,outline='#FAF8F2',width=2*S)
        if n in ['Input_Error','ToastWarning']:
            d=ImageDraw.Draw(q);off=3*S
            d.rounded_rectangle((off,off,q.width-off-1,q.height-off-1),radius=3*S,outline='#D9483F' if n=='Input_Error' else '#E8812C',width=S)
        if n.startswith('BtnPrimary_'):
            # Generated gold foil only on the inner bevel; flat centre stays v1 gold.
            foil=raw('B205').crop((330,140,900,205)).resize((q.width-6*S,2*S),Image.Resampling.LANCZOS)
            q.alpha_composite(tint(foil,state if state in ['hover','pressed','disabled'] else 'normal'),(3*S,3*S))
        if state=='pressed':
            d=ImageDraw.Draw(q);d.line((3*S,2*S,q.width-3*S,2*S),fill='#76664D',width=S)
            d.line((3*S,q.height-3*S,q.width-3*S,q.height-3*S),fill='#FFF2D8',width=S)
        export('T_Skin_'+n,q,margin,'none' if n.startswith('Check_') else 'nine_slice',body,opacity,tc,
               role='v1 body preserved; generated marble and gold bevel',widget='existing skin registry: '+n,sources=[source_id]+(['B205'] if n.startswith('BtnPrimary_') else []),
               content_su=content,focus_overlay=False,focus_outset_su=5 if focus else 0,focus_visual_outset_su=4 if focus else 0,
               glyph_in_png=False,recommended_min_su=[2*margin+12,2*margin+10])
    for nominal,suffix in [(80,''),(64,'_64')]:
        for state,ss in [('normal',''),('active','_Active')]:
            # Broader rim leaves a 54/42 su opening, documented for portrait masks.
            insert=54 if nominal==80 else 42
            export('T_Hud_PortraitFrame'+ss+suffix,round_master('B202',nominal,4,insert,state),0,'none',
                   role='broad marble medallion and bold gold laurels',widget='own/opponent portrait',sources=['B202'],
                   nominal_diameter_su=nominal,insert_diameter_su=insert,canvas_outset_su=4)
    for state in ['Normal','Hover','Pressed','Disabled','Active']:
        export('T_Hud_ActionRing_'+state,round_master('B204',64,4,48,state.lower()),0,'none',
               role='8 su marble gold and enamel action bezel',widget='action discs M/A/G/E',sources=['B204'],
               nominal_diameter_su=64,insert_diameter_su=48,canvas_outset_su=4)
    specs=[('HpPlate',(128,40),[40,10,12,10],'horizontal'),('StatusBanner',(256,56),[48,16,48,16],'horizontal'),
           ('TurnPlate',(144,56),[26,16,26,16],'nine_slice'),('HandTray',(256,56),[28,20,28,20],'horizontal'),
           ('PileFrame',(112,48),[24,20,24,20],'nine_slice'),('ActionPlate',(80,112),[12,12,12,12],'nine_slice')]
    for name,size,ms,stretch in specs:
        margin=min(24,(size[1]-2)//2) if name in ['TurnPlate','HandTray','PileFrame'] else min(ms)
        q=cartouche2(size,ms) if name=='StatusBanner' else frame(size,margin)
        # TurnPlate and piles have larger fixed corner regions than rail depth.
        export('T_Hud_'+name,q,ms,stretch,NAVY,.92,LIGHT,role='navy text body with marble gold ornament',widget=name,
               sources=['B203' if name=='StatusBanner' else 'B201'])
    export('T_Hud_KeyBadge',frame((26,26),6,'#F2C14E',1,source_id='B205'),6,'nine_slice','#F2C14E',1,NAVY,
           role='gold hotkey coin tile, runtime dark letter',widget='action hotkeys',sources=['B205'])
    # Keep the accepted small details, exact holes and glows from B1.
    for n,d in OLD.items():
        if n in ASSETS:continue
        q=Image.open(ART/'kit-b1/masters'/(n+'.png')).convert('RGBA')
        extra={k:v for k,v in d.items() if k not in ['name','size_su','slice_su','stretch','body_color','text_color','files','text_safe_insets_su','source_masters']}
        body=d['body_color'];opacity=.92
        export(n,q,d['slice_su'],d['stretch'],body,opacity,LIGHT,sources=d['source_masters'],**extra)
    write_json(KIT/'assets.json',ASSETS)
    slices={v['path']:{**v['slice_px'],'stretch':d['stretch']} for d in ASSETS.values() for v in d['files'].values()}
    for p in [ART/'slice-margins.json',KIT/'slice-margins.json']:write_json(p,{'unit':'physical px','order':['left','top','right','bottom'],'files':slices})
    catalog();pages=review_pages()
    print(json.dumps({'assets':len(ASSETS),'exports':len(ASSETS)*3,'review_pages':len(pages)}))

if __name__=='__main__':main()
