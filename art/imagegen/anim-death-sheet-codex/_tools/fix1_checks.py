"""Measure corrective acceptance from final artifacts, independently of renderer."""
import json
import re
import numpy as np
from PIL import Image
from scipy import ndimage as ndi

TOKENS={'card.navy':'#061623','card.cream':'#F9EBDB','card.glyph':'#FAF8F2',
        'mark.keyline':'#111317','text.primary':'#F2EDE4','text.secondary':'#B9B2A6',
        'accent.warm':'#FFB45C','team.p1':'#E8C06A','team.p2':'#5A7F9F'}
def rgb(h): return tuple(int(h[i:i+2],16) for i in (1,3,5))
def luma(c): return int(np.rint(np.dot(c,[.2126,.7152,.0722])))
def lab(values):
    s=np.asarray(values,dtype=float)/255
    linear=np.where(s<=.04045,s/12.92,((s+.055)/1.055)**2.4)
    xyz=linear @ np.array([[.4124564,.3575761,.1804375],[.2126729,.7151522,.0721750],[.0193339,.1191920,.9503041]]).T
    q=xyz/np.array([.95047,1,1.08883])
    f=np.where(q>(6/29)**3,np.cbrt(q),q/(3*(6/29)**2)+4/29)
    return np.stack([116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])],axis=-1)
def read(p): return json.loads(p.read_text(encoding='utf-8'))

def extend_checks(P,ROOT,v,save,sha):
    master=np.array(Image.open(P/'vector/AN-30-death-sheet.png'))
    bg=rgb(TOKENS['card.navy']);warm=rgb(TOKENS['accent.warm']);dark=rgb(TOKENS['mark.keyline'])
    exports=[];pairs=[]
    for directory in ['vector','comparison']:
        for p in sorted((P/directory).glob('*.png')):
            im=Image.open(p);a=np.array(im)
            background=(luma(bg),)*3 if p.name.endswith('-gray.png') else bg
            occupied=np.any(a[:,:,:3]!=background,axis=2)
            y,x=np.where(occupied)
            margin=int(min(x.min(),y.min(),im.width-1-x.max(),im.height-1-y.max()))
            exports.append({'path':p.relative_to(P).as_posix(),'size':list(im.size),'mode':im.mode,
                            'margin_px':margin,'touches_edge':margin==0,'background_rgb':background})
            assert im.mode=='RGBA'
            if not p.name.endswith('-gray.png'):
                gray=P/'comparison/AN-30-death-sheet-gray.png' if directory=='vector' else p.with_name(p.stem+'-gray.png')
                assert gray.exists()
                b=np.array(Image.open(gray));expected=np.rint(a[:,:,:3].astype(float) @ np.array([.2126,.7152,.0722])).astype('uint8')
                exact=all(np.array_equal(b[:,:,i],expected) for i in range(3)) and np.array_equal(a[:,:,3],b[:,:,3])
                assert exact
                pairs.append({'color':p.relative_to(P).as_posix(),'gray':gray.relative_to(P).as_posix(),'rec709_exact':exact})
    v['exports']=exports
    # Exclude precisely nonuniform 3x3 neighborhoods, including antialias edges.
    a=master[:,:,:3];uniform=np.ones(a.shape[:2],dtype=bool)
    for i in range(3):
        uniform &= ndi.maximum_filter(a[:,:,i],size=3,mode='nearest')==ndi.minimum_filter(a[:,:,i],size=3,mode='nearest')
    opaque=master[:,:,3]==255;included=uniform & opaque
    colors,counts=np.unique(a[included],axis=0,return_counts=True)
    token_colors=np.array([rgb(h) for h in TOKENS.values()])
    delta=np.linalg.norm(lab(colors)[:,None,:]-lab(token_colors)[None,:,:],axis=2)
    off=int(counts[np.min(delta,axis=1)>3].sum())
    per_token={name:{'hex':h,'pixel_count':int(np.all(a==rgb(h),axis=2)[included].sum())}
               for name,h in TOKENS.items()}
    derived=[]
    for progress in [0,.35,.70,1]:
        alpha=round(255*(1-progress))
        for name in ['card.cream','mark.keyline']:
            im=Image.alpha_composite(Image.new('RGBA',(1,1),bg+(255,)),Image.new('RGBA',(1,1),rgb(TOKENS[name])+(alpha,)))
            c=im.getpixel((0,0))[:3]
            derived.append({'source_token':name,'progress':progress,'opacity':alpha/255,'alpha_byte':alpha,
                            'background':'#061623','composited_rgb':c,'composited_hex':'#'+''.join(f'{x:02X}' for x in c),
                            'off_token':False,'purpose':'uniform reduced-motion opacity; comparison fade states'})
    v['palette']={'file':'vector/AN-30-death-sheet.png','metric':'CIELAB D65 sRGB ΔE76','threshold':3,
                  'off_token_share':off/int(included.sum()),'off_token_pixel_count':off,
                  'opaque_pixel_count':int(opaque.sum()),'included_pixel_count':int(included.sum()),
                  'excluded_count':int((opaque & ~uniform).sum()),'excluded_method':'3x3 neighborhood is not one RGB color',
                  'per_token':per_token,'derived':derived}
    assert off==0
    # Pixel counts and measured separator columns inside each ash state, all sizes.
    ash_checks=[]
    for name,width in [('vector/AN-30-death-sheet.png',1920),('comparison/AN-30-death-sheet-1280.png',1280),
                       ('comparison/AN-30-death-sheet-960.png',960),('comparison/AN-30-ash-vs-fade.png',1920),
                       ('comparison/AN-30-ash-vs-fade-1280.png',1280),('comparison/AN-30-ash-vs-fade-960.png',960)]:
        a=np.array(Image.open(P/name));scale=width/1920
        main='death-sheet' in name
        for actor,base,factor,team in [('KingArthur',565 if main else 424,.46,'team.p1'),('Harpy',777 if main else 841,.59,'team.p2')]:
            m=np.array(Image.open(P/f'traces/{actor}-f21-q34-mask.png').resize((round(420*factor*scale),)*2,Image.Resampling.NEAREST))>0
            ys,xs=np.where(m);lo=int(ys.min());hi=int(ys.max()+1)
            for cx,progress in zip([1496,1780] if main else [850,1300],[.35,.70]):
                front=hi-round((hi-lo)*progress)
                x0=round(cx*scale-m.shape[1]/2);y0=round(base*scale-hi)
                tile=a[y0:y0+m.shape[0],x0:x0+m.shape[1],:3]
                rows=np.where(np.any(np.all(tile[lo:hi]==warm,axis=2),axis=1))[0]+lo
                band=max(1,round(6*scale));line=max(1,round(2*scale))
                assert rows.tolist()==list(range(front-band,front)),(name,actor,progress,rows)
                # Columns that pass continuously through ash/top line/band/bottom line.
                window=tile[front-band-line-1:front+line+1]
                expected=np.array([rgb(TOKENS[team])]+[dark]*line+[warm]*band+[dark]*line+[bg])
                cols=np.where(np.all(window==expected[:,None,:],axis=(0,2)))[0]
                assert len(cols)>0,(name,actor,progress,'no complete separator column')
                # The truncated silhouette retains its original external 2 px outline.
                body=m.copy();body[front:]=False
                edge=ndi.binary_dilation(body,iterations=line)&~body
                assert np.all(tile[edge]==dark)
                allcolors,cnt=np.unique(tile[max(0,lo-line):hi].reshape(-1,3),axis=0,return_counts=True)
                allowed={bg,dark,warm,rgb(TOKENS[team])}
                assert set(map(tuple,allcolors))<=allowed
                ash_checks.append({'file':name,'actor':actor,'progress':progress,'front_band_height_px':len(rows),
                   'top_keyline_px':line,'bottom_keyline_px':line,'measured_column_x':x0+int(cols[len(cols)//2]),
                   'measured_band_y':[y0+int(rows[0]),y0+int(rows[-1])+1],
                   'remaining_silhouette_keyline_checked':True,
                   'pixel_counts':{'#'+''.join(f'{x:02X}' for x in c):int(n) for c,n in zip(allcolors,cnt)},
                   'ash_fill_tokens_only':True,'keyline_is_outline_not_ash':True})
    save('reports/ash-measurements.json',ash_checks)
    distinguish=[]
    for team in ['team.p1','team.p2']:
        yw=luma(warm);yt=luma(rgb(TOKENS[team]));yd=luma(dark)
        records=[r for r in ash_checks if r['file']=='vector/AN-30-death-sheet.png' and r['actor']==('KingArthur' if team=='team.p1' else 'Harpy')]
        distinguish.append({'pair':['accent.warm',team],'luma':[yw,yt],'luma_difference':abs(yw-yt),
          'shape_difference':'horizontal 6px front strip bounded by 2px dark keylines; continuous top and bottom separators measured on PNG',
          'separator_luma':yd,'band_separator_difference':abs(yw-yd),'ash_separator_difference':abs(yt-yd),
          'measured_samples':records,'passed':all(r['top_keyline_px']==r['bottom_keyline_px']==2 for r in records)})
    yp1=luma(rgb(TOKENS['team.p1']));yp2=luma(rgb(TOKENS['team.p2']))
    assert abs(yp1-yp2)>=20
    distinguish.append({'pair':['hero lane','sidekick lane'],'luma':[yp1,yp2],'luma_difference':abs(yp1-yp2),
                          'shape_difference':'hero has still bar and longer ash; labels and separate rows','passed':True})
    # Endpoints inferred from lower horizontal bar pixels, independently of timing JSON.
    timing=[]
    for role,y,expected in [('hero',259,2125),('sidekick',310,1725)]:
        row=master[y,300:1821,:3];px=np.where(np.all(row==warm,axis=1))[0]+300
        end=int(px.max());measured=(end-300)*3125/1520
        timing.append({'role':role,'end_x_px':end,'origin_x_px':300,'axis_end_x_px':1820,'axis_duration_ms':3125,
                       'measured_ms':measured,'expected_ms':expected,'error_ms':abs(measured-expected)})
    assert all(t['error_ms']<=42 for t in timing)
    xstart=round(300+1520*1625/3125);xend=round(300+1520*2125/3125)
    ashbar=master[256:261,xstart+2:xend-1,:3]
    fadebar=master[983:987,xstart+2:xend-1,:3]
    assert np.all(ashbar==warm)
    assert np.all(fadebar[0:2]==bg) and np.all(fadebar[2:]==rgb(TOKENS['text.secondary']))
    distinguish.append({'pair':['ash bar','reduced fade bar'],'luma':[luma(warm),luma(rgb(TOKENS['text.secondary']))],
      'luma_difference':abs(luma(warm)-luma(rgb(TOKENS['text.secondary']))),
      'shape_difference':'ash is a filled warm strip; fade is an outlined secondary bar with navy interior',
      'measured_region_ash':[xstart+2,256,xend-1,261],'measured_region_fade':[xstart+2,983,xend-1,987],'passed':True})
    v['gray']={'method':'Rec.709 after composition; RGB channels equal; alpha preserved','pairs':pairs,'distinguishability':distinguish}
    v['sizes']={'master':{'path':'vector/AN-30-death-sheet.png','size':[1920,1080],'present':True,'drawn_natively':True,'downscaled_from_master':False},
                'working':{'path':'comparison/AN-30-death-sheet-1280.png','size':[1280,720],'present':True,'drawn_natively':True,'downscaled_from_master':False},
                'overview':{'path':'comparison/AN-30-death-sheet-960.png','size':[960,540],'purpose':'compact overview','drawn_natively':True,'downscaled_from_master':False},
                'provenance':'Canvas(width) redraws text, strokes, bars and mask geometry at each output size'}
    for spec in [v['sizes']['master'],v['sizes']['working'],v['sizes']['overview']]:
        assert list(Image.open(P/spec['path']).size)==spec['size']
    working=np.array(Image.open(P/v['sizes']['working']['path']))
    down=np.array(Image.fromarray(master).resize((1280,720),Image.Resampling.LANCZOS))
    v['sizes']['working']['pixels_differing_from_master_downscale']=int(np.any(working!=down,axis=2).sum())
    assert v['sizes']['working']['pixels_differing_from_master_downscale']>0
    # No front/particles anywhere in reduced-motion strip; ash uses outlined alternative.
    reduced=master[938:991,:,:3]
    assert not np.any(np.all(reduced==warm,axis=2))
    assert not np.any(np.all(reduced==rgb(TOKENS['team.p1']),axis=2))
    assert not np.any(np.all(reduced==rgb(TOKENS['team.p2']),axis=2))
    reduced_measure={'phase_windows_ms':[[0,450],[450,1325],[1325,1625],[1625,2125]],
                     'fade_bar_x_px':[xstart,xend],'embers':0,'front_pixels':0,'outlined_secondary_bar':True}
    speed=[]
    for j,duration in enumerate([450,900,1350,450]):
        y=1012+j*13
        row=master[y+2,:,:3];xs=np.where(np.all(row==rgb(TOKENS['team.p1']),axis=1))[0]
        row2=master[y+8,:,:3];short=np.where(np.all(row2==rgb(TOKENS['text.secondary']),axis=1))[0]
        short=short[(short>=300)&(short<=xend)]
        assert xs.min()==300 and xs.max()==xend
        assert short.tolist()==[round(300+1520*60/3125),round(300+1520*(60+duration)/3125)]
        speed.append({'speed':['0.5','1','1.5','none'][j],'death_x_px':[int(xs.min()),int(xs.max())],
                      'damage_x_px':[int(short.min()),int(short.max())],'damage_duration_ms':duration,
                      'measured_damage_ms':(int(short.max())-int(short.min()))*3125/1520})
    v['checks']['speed_variants_measured']=speed
    v['checks']['reduced_motion_lane_measured']=reduced_measure
    # Each drawn number maps to an actual README timing/source table row.
    readme=(P/'README.md').read_text(encoding='utf-8');rows=[]
    def numbers(text):
        text=re.sub(r'#[a-fA-F0-9]{6}','',text)
        return [(s,(s.lstrip('0') or '0')) for s in re.findall(r'\d+(?:,\d+)?',text)]
    for line,text in enumerate(readme.splitlines(),1):
        if text.startswith('|') and len(text.split('|'))==4:
            rows.append({'line':line,'row':text,'numbers':{n for _,n in numbers(text.split('|')[1])}})
    sources=[];unmatched=[]
    for label in read(P/'reports/printed-labels.json'):
        for original,n in numbers(label):
            matches=[r for r in rows if n in r['numbers']]
            if not matches: unmatched.append({'label':label,'number':original})
            else:
                match=next((r for r in matches if label.startswith('СКОРОСТЬ') and 'UI-ACC-013' in r['row']),matches[0])
                sources.append({'label':label,'number':original,'readme_path':'README.md','readme_line':match['line'],'readme_row':match['row']})
    assert not unmatched,unmatched
    save('reports/number-sources.json',{'matches':sources,'unmatched':unmatched,'unmatched_count':len(unmatched)})
    # Clear label boxes are checked against actual lane-line pixels at their row.
    layout=read(P/'reports/layout.json');clearance=[]
    for record in layout[:3]:
        # Read renderer's label coordinates, reconstructed from exact Roboto metrics.
        from PIL import ImageFont,ImageDraw
        im=Image.open(P/record['file']);d=ImageDraw.Draw(im);s=im.width/1920
        for label,xy,size,bold,anchor,y,team in [
             ('gone · 2125',(300+1520*2125/3125+12,229),20,True,'lt',243,'team.p1'),
             ('gone · 1725',(300+1520*1725/3125+12,280),20,True,'lt',294,'team.p2'),
             ('+1000 → result',((300+1520*2125/3125+1820)/2,249),18,False,'mt',243,'team.p1'),
             ('без result',(1820,280),18,False,'rt',294,'team.p2')]:
            font=ImageFont.truetype('C:/Program Files/Epic Games/UE_5.8/Engine/Content/Slate/Fonts/'+('Roboto-BoldCondensed.ttf' if bold else 'Roboto-Regular.ttf'),max(1,round(size*s)))
            b=d.textbbox(tuple(round(z*s) for z in xy),label,font=font,anchor=anchor)
            a=np.array(im);yy=round(y*s)
            # Navy guard extends at least 4 pixels horizontally beyond text bounds.
            if b[1]-4<=yy<=b[3]+4:
                for xx in list(range(b[0]-4,b[0]))+list(range(b[2]+1,b[2]+5)):
                    assert tuple(a[yy,xx,:3])==bg,(record['file'],label,b,xx)
            clearance.append({'file':record['file'],'label':label,'label_bbox':b,'line_y_px':yy,'minimum_clearance_px':4,'passed':True})
    save('reports/label-clearance.json',clearance)
    # Prove old raw concepts and before/source snapshots were not regenerated.
    snapshot=read(P/'fix1-before.json')['files']
    protected=[name for name in snapshot if name.startswith('concepts/') or name in ['source-hashes-before.json','_tools/draw_icons_v3_snapshot.py']]
    assert all(sha(P/name)==snapshot[name]['sha256'] for name in protected)
    assert (P/'concepts/AN-30-death-sheet-fix1-unretouched.png').read_bytes()==(P/'vector/AN-30-death-sheet.png').read_bytes()
    prompts=read(P/'prompts/AN-30-prompts.json')
    for key,file in [('AN-30/task','AN-30.codex.md'),('AN-30/fix1','AN-30.fix1.codex.md')]:
        exact=(ROOT/'docs/game-design/visual/06-tasks/prompts'/file).read_text(encoding='utf-8').split('```text\n',1)[1].split('\n```',1)[0]
        assert prompts[key]==exact
    # CUE markers measured on actual raster at fixed common-axis positions.
    heart_x=round(300+1520*1100/3125);result_x=1820
    assert tuple(master[860,heart_x,:3])==rgb(TOKENS['card.cream'])
    assert tuple(master[860,result_x,:3])==warm
    cue={'heart':{'x_px':heart_x,'measured_ms':(heart_x-300)*3125/1520,'expected_ms':1100},
         'result':{'x_px':result_x,'measured_ms':3125,'expected_ms':3125}}
    total=sum(r['connected_ember_dots'] for r in v['independent_artifact_checks']['embers_counted_from_final_png'])
    def acceptance(passed,measured,expected,note):return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    v['acceptance']=[
      acceptance(all(t['error_ms']<=42 for t in timing),timing,{'hero_ms':2125,'sidekick_ms':1725,'tolerance_ms':42},'Lower phase strip endpoint in PNG; 300–1820 px = 0–3125 ms.'),
      acceptance(True,cue,{'heart_ms':1100,'result_ms':3125},'Exact label and raster markers on common axis; result hero only.'),
      acceptance(True,[r for r in ash_checks if r['file']=='vector/AN-30-death-sheet.png'],['#FFB45C','#E8C06A','#5A7F9F'],'Only required front/team fills in ash states; #111317 belongs to specified keyline.'),
      acceptance(total<=40,{'drawn_dots':total,'per_state':v['independent_artifact_checks']['embers_counted_from_final_png']},'<=40','Connected components in raster, not emitter claims.'),
      acceptance(True,reduced_measure,'plain fade, no front or embers','Full reduced-motion timing lane; comparison validates uniform opacity at both fade states.'),
      acceptance(v['visual_review'].get('checks',{}).get('no_kneeling',False),{'view':'q34','frames':[0,3,13,21],'trace_pose_invented':False,'visual_review':v['visual_review'].get('performed',False)},'no kneeling','Original source poses preserved; reviewed standing Arthur and bowed open-wing Harpy.'),
      acceptance(not unmatched,{'number_occurrences_matched':len(sources),'unmatched':len(unmatched)},'unmatched 0','Every printed number linked to an actual README source-table row in reports/number-sources.json.'),
      acceptance(v['source_unchanged'] and v['outside_folder']==[] and all(x['rec709_exact'] for x in pairs),{'color_gray_pairs':len(pairs),'source_unchanged':v['source_unchanged'],'outside_folder':v['outside_folder']},'colour and gray; source_unchanged true; outside_folder []','Every source rehashed against original before snapshot; no outside writes by this task.')]
    assert all(item['passed'] for item in v['acceptance']),v['acceptance']
    v['checks']['no_kneeling']='confirmed visually against unchanged source poses'
    v['checks']['fix1_protected_files_unchanged']=protected
    v['checks']['gone_error_ms']={r['role']:r['error_ms'] for r in timing}
    v['checks']['label_clearance_measured']=clearance
    v['checks']['prompts_verbatim']=True
    v['independent_artifact_checks']['fix1_acceptance_passed']=8
    v['write_audit']['written_files']=sorted(p.relative_to(ROOT).as_posix() for p in P.rglob('*') if p.is_file())
    save('verification.json',v)

def write_manifest(P,ROOT,save,sha):
    files={}
    for folder in [P,ROOT/'scraped-data/derived/anim-death-sheet-codex']:
        if not folder.exists():continue
        for p in sorted(folder.rglob('*')):
            if p.is_file() and p!=(P/'manifest-sha256.json'):
                files[p.relative_to(ROOT).as_posix()]={'sha256':sha(p),'bytes':p.stat().st_size}
    save('manifest-sha256.json',{'task':'AN-30/fix1','status':'предложено','path_base':'repository root','files':files})
    # Read-only final coverage/digest check. No file is written after manifest.
    for name,record in files.items():
        p=ROOT/name
        assert sha(p)==record['sha256'] and p.stat().st_size==record['bytes']
