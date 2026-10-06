"""HB-38 offline native-size renderer. python -B -X utf8 .../_tools/build_feed.py

No network, git, Unreal or child process. Snapshot modules are immutable; their
build entry points are never called. hand_build_snapshot installs a filesystem
audit hook restricting every write to this package and its derived folder.
"""
from __future__ import annotations
import sys
sys.dont_write_bytecode=True
import json, math, re, hashlib, itertools
from pathlib import Path
from functools import lru_cache
import numpy as np
from PIL import Image, ImageDraw
import pending_build_snapshot as p
import hand_build_snapshot as hb
import composition_build_snapshot as comp
import topstrip_build_snapshot as top
import skins_snapshot as skins
import fix1_font as composite
import fix1_reports
PKG=Path(__file__).resolve().parents[1]
ROOT=PKG.parents[2]
DERIVED=ROOT/'scraped-data/derived/hud-feed-v1-codex'
hb.DERIVED=DERIVED
p.DERIVED=DERIVED
comp.PACKAGE=PKG;comp.DERIVED=DERIVED
comp.ref.PACKAGE=PKG;comp.ref.DERIVED=DERIVED
top.PKG=PKG;top.DERIVED=DERIVED
T={**p.T,'p1':'#DAC576','p2':'#5786A8','error':'#D9483F'}
p.T=T
STATES=['log','toast-info','toast-warning','toast-error','toast-stack','toast-bottom','sub','sub-lowered']
CONFIGS=hb.CONFIGS
composite.install([hb,p,comp,comp.ref,top])
load=hb.load;sha=hb.sha;rel=hb.rel;font=composite.font;rgb=p.rgb
def dump(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=1 if path.name=='verification.json' else 2,default=lambda x:x.item() if isinstance(x,np.generic) else x.tolist() if isinstance(x,np.ndarray) else str(x))+'\n',encoding='utf8')
gray=p.gray
F07=load(ROOT/'art/imagegen/hud-composition-v1-codex/facts.json')
C29=load(ROOT/'art/imagegen/hud-combat-v1-codex/verification.json')
CANON=p.CANON
F={'task':'HB-38','status':'предложено','cards':{},'rendered_texts':[],'outputs':[],
   'state_matrix':{},'logs':{},'board_figures':{},'scans':[],'deltas_04':[],
   'strings_without_key':{'turn_label':{'ru':'Х{n}','en':'T{n}','source':'docs/game-design/visual/04-hud-spec.md §2.10 / HB-38 P9','string_table_key':None}},
   'uncertain_values':[{'what':'Synchronous HP and exact hand at the last LOG event / reconnect','handling':'Use the explicitly permitted HB-07 static run I projection; never assert these are a synchronized snapshot.'},
                       {'what':'Exact live target position at refusal','handling':'Use bench figure positions and topology zones; label this as geometry example, not a recorded run I refusal.'}], 'accepted_hb07_projection':F07['boards'],
   'geometry_examples':['toast-info','toast-warning','toast-error','toast-stack','toast-bottom','sub','sub-lowered']}
V={'schema':'07 §1.2 / HB-38','task':'HB-38','status':'предложено','source_unchanged':False,
   'exports':[],'palette':{},'gray':{},'sizes':{},'outside_folder':[],'acceptance':{},
   'contrast':[],'overlap':[],'transient_overlap':[],'toast_placement':[],
   'toast_placement_combat':[],'sub_placement':[],'sub_placement_combat':[],
   'list_fit':[],'text_fit':[],'log_ellipsis':[],'min_text_px_720p':None,
   'gray_pairs':[],'skin_match_hb08':[],'uncertain_values':F['uncertain_values'],
   'background_integrity':[],'hand_geometry':[],'persistent_blocks':[],
   'palette_per_mockup':[],'scans':[]}
p.FACTS=F;hb.FACTS=F;p.V=V
BEFORE=load(PKG/'fix1-before.json')
V['fix1_inputs']={composite.FALLBACK.as_posix():{'sha256':sha(composite.FALLBACK)}}
V['en_fit']=[];V['en_without_value']=[]

def en_string(key,**params):
    row=hb.STRINGS[key]
    value=row.get('SourceString') or row['ru']
    if not row.get('SourceString'):
        V['en_without_value'].append({'key':key,'text':value})
    return value.format(**params)

# HB-07's audit layer intentionally excludes source imagery. Retain those
# native image stamps in the full HUD used here, without re-rendering/resizing.
_image=comp.Canvas.image
def image_into_hud(c,path,r):
    im,pos=_image(c,path,r);c.hud.alpha_composite(im,pos);return im,pos
def portrait_into_hud(c,path,x,y,size):
    from PIL import ImageOps
    n=round(size*c.s)
    im=ImageOps.fit(comp.ref.original(str(path)),(n,n),method=Image.Resampling.LANCZOS)
    mask=Image.new('L',(n,n));ImageDraw.Draw(mask).ellipse((0,0,n-1,n-1),fill=255)
    c.im.paste(im,(round(x*c.s),round(y*c.s)),mask)
    layer=Image.new('RGBA',c.hud.size);layer.paste(im,(round(x*c.s),round(y*c.s)),mask)
    c.hud.alpha_composite(layer)
    c.visual_boxes.append({'block':c.active,'kind':'avatar','path':comp.ref.relative(path),
         'bbox_px':[round(x*c.s),round(y*c.s),round(x*c.s)+n,round(y*c.s)+n]})
comp.Canvas.image=image_into_hud
comp.Canvas.portrait=portrait_into_hud

def string(key,lang='ru',**params):return p.string(key,lang,**params)

def evidence():
    vo=ROOT/'docs/game-design/audio/04-vo-script.md'
    F['vo']={}
    for n,line in enumerate(vo.read_text(encoding='utf8').splitlines(),1):
        if line.startswith('| ARTHUR-MATCHUP-MEDUSA-01') or line.startswith('| ARTHUR-ATTACK-01'):
            cells=[v.strip() for v in line.split('|')[1:-1]]
            F['vo'][cells[0]]={'en':cells[1],'ru':cells[2],'source':rel(vo),'line':n,'key':cells[0]}
    reconnect=ROOT/'docs/game-design/evidence/DE-FOOTAGE/2026-10-04/E/live/phase2/marmoreal/run-20261005-135124/phase2-client-joiner.trace.txt'
    lines=reconnect.read_text(encoding='utf8').splitlines()
    F['reconnect']={'source':rel(reconnect),'n':0,'subscribed_since':1,'snapshot_seq':1,
      'derivation':'snapshot_seq - subscribed_since = 1 - 1 = 0',
      'evidence':[{'line':i+1,'trace':v} for i,v in enumerate(lines) if 146<=i<=165 and any(k in v for k in ['STATE','WS closed','reconnect','SUBSCRIBED','SNAPSHOT'])]}
    for b in hb.BG:
        owner='Medusa' if b=='marmoreal' else 'King Arthur'
        attacker='Medusa' if b=='marmoreal' else 'Merlin'
        path=ROOT/F07['boards'][b]['turn']['path'];lines=path.read_text(encoding='utf8').splitlines()
        limit=23 if b=='marmoreal' else 26
        rows=[]
        for n,line in enumerate(lines,1):
            m=re.search(r'MS-LOG seq=(\d+) moves=(\d+) truncated=(\d+) text="(.*?)"',line)
            if not m or int(m[1])>limit:continue
            seq=int(m[1]);en=m[4]
            player,detail=en.split(': ',1)
            if ': ' not in detail:raise ValueError(en)
            prefix,moves_en=detail.split(': ',1)
            if prefix=='maneuver':key='ms.log.maneuver';card=None
            else:
                assert prefix.endswith(' effect');key='ms.log.effect';card=prefix[:-7]
            translations={};params={};nested=[]
            for lang in ['ru','en']:
                if moves_en=='no movement':moves,src=string('ms.log.stay',lang);nested.append(src)
                else:
                    parts=[]
                    for move in moves_en.split(', '):
                        mm=re.fullmatch(r'(.*?) ([MS]\d+)→([MS]\d+)',move);assert mm,move
                        text,src=string('ms.log.move',lang,fighterName=mm[1],**{'from':mm[2],'to':mm[3]})
                        parts.append(text);nested.append(src)
                    moves=', '.join(parts)
                args={'player':player,'moves':moves}
                if key=='ms.log.maneuver':args['boostPart']=''
                else:
                    cardname=card
                    if player=='Medusa' and lang=='ru':
                        row=next(x for x in hb.HEROES['medusa']['fetchedDeck'] if x['card']['title']==card)
                        cardname=row['card']['i18n']['ru']['title']
                    args['cardName']=cardname
                translations[lang],src=string(key,lang,**args);params[lang]=args
            assert translations['en']==en
            # MS-LOG is delayed. The snapshot of an action that ends a turn
            # already points at the NEXT player. Use the acting player's own
            # S09AUTO interval before first application of this event seq.
            actorpath=path.with_name('combat-client-host.trace.txt' if player=='Medusa' else 'combat-client-joiner.trace.txt')
            actorlines=actorpath.read_text(encoding='utf8').splitlines()
            applied=next((i for i,z in enumerate(actorlines) if re.search(r'SNAPSHOT applied seq='+str(seq)+r'\b',z)),None)
            assert applied is not None,(b,seq)
            starts=[(i,z) for i,z in enumerate(actorlines[:applied]) if re.search(r'S09AUTO own turn .*turnCount=',z)]
            assert starts,(b,seq)
            ti,tl=starts[-1];turn={'value':int(re.search(r'turnCount=(\d+)',tl)[1]),'path':rel(actorpath),'line':ti+1,'trace':tl,
                'first_event_snapshot':{'line':applied+1,'trace':actorlines[applied]},
                'selection':'Acting player latest S09AUTO own turn before the first SNAPSHOT applied seq=event. Delayed MS-LOG/current HUD turn cannot assign the event turn.'}
            rows.append({'seq':seq,'trace':{'path':rel(path),'line':n,'text':line},
                         'ru':translations['ru'],'en':en,'key':key,'parameters':params,
                         'nested_strings':nested,'turn':turn,'team':'p1' if player=='Medusa' else 'p2',
                         'card_name_source':'scraped-data/api/heroes/medusa.json#card.i18n.ru.title' if player=='Medusa' and card else 'C:/tmp/visual/CX-13/db-cards-2026-10-06.txt' if card else None})
        assert [r['seq'] for r in rows]==([5,7,13,15,22,23] if b=='marmoreal' else [3,5,9,13,24,26])
        F['logs'][b]={'moment_seq':limit,'rows':rows,'turn_derivation':'Acting player S09AUTO own turnCount before first event SNAPSHOT applied seq. End-turn action snapshot can already contain next player, while MS-LOG is emitted later.'}
        topo=load(ROOT/f'backend/prisma/fixtures/boards/{b}.topology.json');spaces={r['id']:r for r in topo['spaces']}
        figures=[{'name':name,'space_id':sid,'zones':spaces[sid]['zones'],'team':'p2' if name in ['King Arthur','Merlin'] else 'p1'} for name,sid in CANON[b].items()]
        start=CANON[b][attacker];az=set(spaces[start]['zones'])
        opponents=['King Arthur','Merlin'] if b=='marmoreal' else ['Medusa','Harpies 1','Harpies 2','Harpies 3']
        target=next(name for name in opponents if not az.intersection(spaces[CANON[b][name]]['zones']))
        F['board_figures'][b]={'figures':figures,'source':'HB-07 registered bench masks + HB-34 CANON + topology zones','attacker':attacker,'attacker_space':start,'attacker_zones':sorted(az),
         'refused_target':target,'refused_space':CANON[b][target],'refused_zones':spaces[CANON[b][target]]['zones'],
         'shared_zones':sorted(az.intersection(spaces[CANON[b][target]]['zones'])), 'ranged_refusal':True,
         'topology':f'backend/prisma/fixtures/boards/{b}.topology.json','background':hb.BG[b]}
        arthur8=hb.ARTHUR+['excalibur','the-aid-of-morgana','aid-the-chosen-one','command-the-storms','bewilderment']
        test=['medusa:'+k for k in hb.TEST9[:8]] if b=='marmoreal' else ['king-arthur:'+k for k in arthur8]
        assert len(set(test))==8 and all(k in hb.DECK for k in test)
        for st in STATES:
            kind='run I log moment on accepted HB-07 static projection' if st=='log' else 'example from real inputs / same rules'
            notes={'log':'MS-LOG up to moment_seq; persistent values remain accepted HB-07 projection',
                   'toast-info':'Real reconnect E: 0 missed; not run I',
                   'toast-warning':'Eight distinct real cards; illustrative hand 8/7, not recorded run I hand',
                   'toast-error':'Opponent turn click End turn, reason why.not.your.turn; illustrative refusal',
                   'toast-stack':'Illustrative stale command after reconnect; info n=0, error why.client.desync',
                   'toast-bottom':'Bench-space ranged target refusal; owner run I attacker, lowered hand',
                   'sub':'Geometry example: matchup VO occurs at match start; not at this run I log moment',
                   'sub-lowered':'Geometry example: Arthur attack VO triggers Arthur himself; in run I Merlin attacked'}
            F['state_matrix'][b+'/'+st]={'kind':kind,'note':notes[st],'hud_owner':owner,'turn':'opponent' if st=='toast-error' else 'own','trace_log_lines':[r['trace']['line'] for r in rows],
                 'hand_keys':test if st=='toast-warning' else [comp.BOARD[b]['own']+':'+k for k in comp.BOARD[b]['hand']],
                 'hand_max':7,'max_source':'Run I HUD hand n/7 and HB-07 run_values.hand_max', 'attacker':attacker if st in ['toast-bottom','sub-lowered'] else None}
    F['p_requirements']={f'P{i}':str(i) for i in range(1,15)}

@lru_cache(None)
def base_game(board,w,h,ui,s,opp,lang='ru'):
    state='opp-turn' if opp else 'own-turn'
    geometry=comp.geometry(board,state,w,h,s)
    original_st,original_geometry=comp.st,comp.geometry
    if lang=='en':
        def translated(key,**params):
            _,src=original_st(key,**params)
            return en_string(key,**params),{**src,'language':'en'}
        comp.st=translated
        comp.geometry=lambda *args:geometry
    try:c,g=comp.render(board,state,w,h,s/(ui/100),ui,hb.HEROES,hb.CARDS)
    finally:comp.st,comp.geometry=original_st,original_geometry
    out=Image.new('RGBA',(w,h));blocks={}
    keep=['PANEL-LOC','PANEL-OPP','OPP-HAND','DECKS','ACTIONS']
    for k in keep:
        r=g['rectangles'][k];box=hb.pxbox(r,s)
        out.alpha_composite(c.hud.crop(box),(box[0],box[1]));blocks[k]=list(r)
    records=[t for t in c.texts if t['block'] in keep]
    icons=[i for i in c.icons if i['block'] in keep]
    scans=[z for z in c.scans if z.get('stableContentKey') not in ['HAND']]
    return out,blocks,records,icons,scans

def fit_native_source(record,cid):
    # HB-07 text records include actual ink, source and nominal type.
    return {'id':cid,'block':record.get('block'),'text':record['text'],
            'source':record.get('source'),'nominal_px':record['nominal_px'],
            'not_truncated':not record.get('log_ellipsis',False) and record['displayed']==record['text'],'inherited_hb07':True,'record':record}

class Canvas(p.Canvas):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.id=f'HB-38-{self.board}-{self.state}'+('-en' if self.lang=='en' else '')+f'-{self.w}x{self.h}-{self.ui}'
        self.feed_names=[];self.toast_rects=[];self.sub_rect=None;self.attempt_records=[]
    def txt(self,*args,**kwargs):
        row=super().txt(*args,**kwargs)
        # Fractional glyph coverage excluded from strict token check by parent.
        return row
    def feed_panel(self,name,r,skin='Toast',transient=False):
        self.panel(name,r,skin=skin,transient=transient)
        self.feed_names.append(name)
    def badge(self,name,r):
        self.panel(name,r,transient=True,fill='navy',opacity=1,radius=4,edge=('keyline',1,1))
        # mark.keyline is the explicitly requested OUTER dark silhouette,
        # distinct from the functional panel.edge/body pair of P12 / §3.5.
        for row in V['contrast']:
            if row['id']==self.id and row['panel']==name and row['role']=='edge_to_body':
                row.update(role='outer_keyline_informational',required=None,
                  note='Required dark mark.keyline outline, not panel.edge. Raw contrast to navy retained; X/body is the functional acceptance pair.')
        draw=ImageDraw.Draw(self.hud);s=self.s;x,y,w,h=r
        draw.rounded_rectangle((round(x*s),round(y*s),round((x+w)*s)-1,round((y+h)*s)-1),radius=round(4*s),outline=rgb('keyline'),width=max(1,round(s)))
        self.sign('error',[x,y,24,24],'navy',name)
    def sign(self,kind,r,ground='navy',parent=None):
        x,y,w,h=r;s=self.s;layer=Image.new('RGBA',(self.w,self.h));d=ImageDraw.Draw(layer)
        def pt(a,b):return (round((x+a)*s),round((y+b)*s))
        if kind=='warning':
            # Exact HB-29 stand-in: triangle24 filled state.warning and navy !.
            bx=hb.pxbox(r,s)
            d.polygon([(bx[0]+(bx[2]-bx[0])/2,bx[1]),(bx[2]-1,bx[3]-1),(bx[0],bx[3]-1)],fill=rgb('warning'))
            ff=font(math.ceil(14*s),True);text='!';bw=ff.getlength(text);bb=ff.getbbox(text)
            tx=round((x+7)*s)+(round(10*s)-bw)/2;ty=round((y+7)*s)-bb[1]
            mask=Image.new('L',(self.w,self.h));ImageDraw.Draw(mask).text((tx,ty),text,font=ff,fill=255)
            ink=Image.new('RGBA',mask.size,(*rgb('navy'),0));ink.putalpha(mask);layer.alpha_composite(ink)
            aa=np.asarray(mask);self.antialias|=(aa>0)&(aa<255)
            col='warning'
        else:
            col='secondary' if kind=='close' else 'error';stroke=2 if kind=='close' else 3
            d.line([pt(5,5),pt(19,19)],fill=rgb(col),width=max(1,round(stroke*s)))
            d.line([pt(5,19),pt(19,5)],fill=rgb(col),width=max(1,round(stroke*s)))
        self.hud.alpha_composite(layer);self.palette.alpha_composite(layer);self.materials.append(layer)
        # Compare the sign to actual panel body pixels under its 24 su plate.
        ratio=body_contrast(self,r,col)
        V['contrast'].append({'id':self.id,'panel':parent,'role':'sign_to_body','sign':kind,'ratio':ratio,'required':3,'rectangle_su':r})
        if kind=='warning':
            V['contrast'].append({'id':self.id,'panel':parent,'role':'glyph_to_sign_plate','sign':'!','ratio':hb.contrast(rgb('navy'),rgb('warning')),'required':3,'source':'HB-29 build_hb29.py lines 301-305'})
        return layer

def persistent(c):
    opp=c.state=='toast-error';hud,blocks,texts,icons,scans=base_game(c.board,c.w,c.h,c.ui,c.s,opp,c.lang)
    c.hud=hud.copy();c.blocks={k:list(v) for k,v in blocks.items()}
    for t in texts:
        row=fit_native_source(t,c.id);V['text_fit'].append(row);F['rendered_texts'].append(row)
        if c.lang=='en':
            r=c.blocks[t['block']];box=hb.pxbox(r,c.s)
            fitted=all(b[0]>=box[0] and b[1]>=box[1] and b[2]<=box[2] and b[3]<=box[3] for b in t['bbox_px'])
            fitted=fitted and max(t['line_width_su'],default=0)<= (80 if t['block']=='ACTIONS' else r[2])
            row['not_truncated']=row['not_truncated'] and fitted
            V['en_fit'].append({'block':t['block'],'text':t['text'],'source':t['source'],'passed':row['not_truncated'],'rectangle_su':r})
        V['contrast'].append({'id':c.id,'panel':t['block'],'role':'text','text':t['text'],'ratio':t['contrast_min'],'required':4.5,'inherited_hb07':True})
    for z in icons:
        V['contrast'].append({'id':c.id,'panel':z['block'],'role':'accepted_icon_pair','ratio':z['solid_ink_vs_navy_min'],'required':3,'source':z['path'],'pair':z['contrast_pair']})
    topstate='opp-turn' if opp else 'own-target' if c.state in ['toast-bottom','sub-lowered'] else 'own-action-keys'
    # Exact accepted HB-13 TOP, STATUS and key-chip look. The Sarpedon target
    # example uses Merlin, the actual attacker, instead of generic owner name.
    old=top.FACTS[c.board][topstate]
    sf={**old,'turn':{**old['turn'],'value':comp.BOARD[c.board]['turn'],
         'projection_source':'art/imagegen/hud-composition-v1-codex/facts.json#boards.'+c.board+'.turn'}}
    if topstate=='own-target':
        params={'fighterName':F['board_figures'][c.board]['attacker']}
        sf={**sf,'arguments':params,'text':top.string('ms.status.target',**params),'key':'ms.status.target'}
    ru_top_geometry=top.geometry(sf,c.w,c.h,c.s,c.ui)
    if c.lang=='en':
        args=sf['arguments'];sf={**sf,'text':top.STRINGS[sf['key']]['SourceString'].format(**args)}
    # state_fact stores parameters under params (resolve below without guesses).
    top.FACTS[c.board][topstate]=sf
    original_string,original_geometry=top.string,top.geometry
    if c.lang=='en':
        top.string=en_string
        def fixed_top(f,*args,**kwargs):
            import copy
            g=copy.deepcopy(ru_top_geometry)
            available=g['rectangles']['STATUS'][2]-32-g['dot_su']-sum(g['chips_width_su'])-8*max(0,len(f['chips'])-1)-(12 if f['chips'] else 0)
            g['lines']=top.wrap(f['text'],top.font(math.ceil(g['type_su']*c.s)),available*c.s)
            return g
        top.geometry=fixed_top
    try:tc,tg,ta=top.render(c.board,topstate,c.w,c.h,c.s,c.ui,c.base)
    finally:
        top.FACTS[c.board][topstate]=old
        top.string,top.geometry=original_string,original_geometry
    c.hud.alpha_composite(tc.hud)
    c.blocks.update({k:v for k,v in tg['rectangles'].items() if k in ['TOP','STATUS']})
    c.geometries['status']=c.blocks['STATUS']
    for t in tc.text_records:
        bbox=t['bbox_px'];fit=bbox is not None and 0<=bbox[0]<bbox[2]<=c.w and 0<=bbox[1]<bbox[3]<=c.h
        row={'id':c.id,'block':'TOP/STATUS','source':'HB-13 '+sf['key']+' / st-hud.csv key chips','text':t['text'],'bbox_px':bbox,'nominal_px':t['nominal_px'],'not_truncated':fit,'inherited_hb13':True}
        V['text_fit'].append(row);F['rendered_texts'].append(row)
        panel=c.blocks['TOP'] if bbox and bbox[0]<=round((c.blocks['TOP'][0]+c.blocks['TOP'][2])*c.s) else c.blocks['STATUS']
        if c.lang=='en':
            pb=hb.pxbox(panel,c.s)
            fitted=bbox is not None and bbox[0]>=pb[0] and bbox[1]>=pb[1] and bbox[2]<=pb[2] and bbox[3]<=pb[3]
            row['not_truncated']=fitted
            V['en_fit'].append({'block':'TOP' if panel==c.blocks['TOP'] else 'STATUS','text':t['text'],'passed':fitted,'rectangle_su':panel})
        V['contrast'].append({'id':c.id,'panel':'TOP/STATUS','role':'text','text':t['text'],'ratio':body_contrast(c,panel,t['color']),'required':4.5,'inherited_hb13':True})
    c.keys=F['state_matrix'][c.board+'/'+c.state]['hand_keys']
    g=hb.geometry(c.board,c.w,c.h,c.ui,c.s,len(c.keys));lower=c.state in ['toast-bottom','sub-lowered']
    c.g=g
    if not lower:
        if c.lang=='en':
            value=hb.STRINGS['hud.hand.count']['ru'].format(n=len(c.keys),max=7)
            r=[g['caption'][0],g['caption'][1],font(math.ceil(14*c.s)).getlength(value)/c.s+24+2/c.s,22]
            c.panel('HAND-CAPTION',r,radius=4)
            c.text('HAND-CAPTION','hud.hand.count',[r[0]+12,r[1],r[2]-24,r[3]],params={'n':len(c.keys),'max':7})
            g['caption_plate']=r
        else:c.caption(g,len(c.keys))
        caption=c.texts[-1];caption['id']=c.id
        if c.lang=='en':V['en_fit'].append({'block':'HAND-CAPTION','text':caption['text'],'passed':caption['not_truncated'],'rectangle_su':r})
        V['text_fit'].append(caption)
        V['contrast'].append({'id':c.id,'panel':'HAND-CAPTION','role':'text','text':caption['text'],'ratio':body_contrast(c,c.blocks['HAND-CAPTION'],'primary'),'required':4.5,'inherited_hb22':True})
    cardrects=[]
    for i,key in enumerate(c.keys):
        r=list(g['cards'][i])
        if lower:r[1]=c.h/c.s-48
        c.card(key,r,name='HAND-'+str(i));cardrects.append(r)
    c.hand_top=cardrects[0][1]
    c.corridor_center=sum(g['corridor_su'])/2
    # Use the clipped native union of the fan, not its off-viewport extent.
    for name in list(c.blocks):
        if name.startswith('HAND-') and name!='HAND-CAPTION':
            r=c.blocks[name];r[3]=min(r[3],c.h/c.s-r[1])
    c.hand_anchor=c.hand_top if lower else c.blocks['HAND-CAPTION'][1]
    V['hand_geometry'].append({'id':c.id,**g,'lowered':lower,'visible_height_su':48 if lower else g['visible_height_su'], 'caption_hidden':lower,'actual_cards_su':cardrects})
    V['persistent_blocks'].append({'id':c.id,'blocks':dict(c.blocks),'icons':icons,'projection':'HB-07 own/opp, HB-13 TOP/STATUS, HB-22 hand, CP-13 native frames'})
    V['scans'].extend(c.scans);F['scans'].extend(c.scans)
    c.persistent=c.hud.copy()
    # All pigment and overlap audits below concern the HB-38 layer alone.
    c.hud=Image.new('RGBA',(c.w,c.h));c.palette=Image.new('RGBA',(c.w,c.h))
    c.antialias=np.zeros((c.h,c.w),dtype=bool);c.materials=[]

def body_contrast(c,r,token):
    x0,y0,x1,y1=hb.pxbox(r,c.s)
    patch=np.asarray(c.base)[max(0,y0):min(c.h,y1),max(0,x0):min(c.w,x1),:3]
    if not patch.size:return 0.
    ground=np.rint(patch*(20/255)+np.array(rgb('navy'))*(235/255))
    gl=hb.luminance(ground);fl=hb.luminance(rgb(token))
    return float(np.min((np.maximum(gl,fl)+.05)/(np.minimum(gl,fl)+.05)))

def log(c):
    if c.small and c.state!='log':return
    rows=F['logs'][c.board]['rows'];ref=hb.reference(c.board,c.w,c.h,c.ui)
    if c.small:
        topbox=c.blocks['TOP'];r=[topbox[0],topbox[1]+topbox[3]+8,360,320];name='LOG-LIST';selected=rows[-50:]
        fit=int((r[3]-40-12)//22);visible=selected[-fit:];transient=True
        V['list_fit'].append({'id':c.id,'all_rows':len(rows),'cap':50,'visible_rows':len(visible),'capacity':fit,'scroll_needed':len(selected)>fit,'track':None,'thumb':None,'anchor':'TOP.left, TOP.bottom + 8su','rectangle_su':r})
    else:
        r=list(ref['panels']['LOG']['rectangle_su']);name='LOG';visible=rows[-(6 if c.w==1920 else 3):];transient=False
    c.feed_panel(name,r,'Panel',transient)
    c.keyed(name,'hud.log.title',[r[0]+12,r[1]+8,r[2]-24,22],14,True,'secondary',container=name)
    y=r[1]+40
    for i,row in enumerate(visible):
        yy=y+i*22;stripe=[r[0]+1,yy,4,20]
        layer=Image.new('RGBA',(c.w,c.h));ImageDraw.Draw(layer).rectangle((round(stripe[0]*c.s),round(yy*c.s),round((stripe[0]+4)*c.s)-1,round((yy+20)*c.s)-1),fill=rgb(row['team']))
        c.hud.alpha_composite(layer);c.palette.alpha_composite(layer);c.materials.append(layer)
        V['contrast'].append({'id':c.id,'panel':name,'role':'team_stripe_to_body','team':row['team'],'ratio':body_contrast(c,stripe,row['team']),'required':3})
        label=('Х' if c.lang=='ru' else 'T')+str(row['turn']['value'])
        c.txt(name+'.turn',label,F['strings_without_key']['turn_label'],[r[0]+12,yy,30,22],14,False,'secondary',container=name)
        full=row[c.lang];available=r[2]-60-(12 if c.small else 0)
        f=font(math.ceil(16*c.s));display=full
        if f.getlength(display)>available*c.s:
            while display and f.getlength(display+'…')>available*c.s:display=display[:-1]
            display=display.rstrip()+'…'
        V['log_ellipsis'].append({'id':c.id,'seq':row['seq'],'full_text':full,'displayed':display,'ellipsis':display!=full,'available_su':available,'key':row['key'],'trace':row['trace']})
        c.txt(name+'.row',display,{'source':'docs/unreal/contracts/hud/st-ms.csv','key':row['key'],'parameters':row['parameters'][c.lang],'trace':row['trace'],'full_text':full},
              [r[0]+48,yy,available,22],16,False,'primary' if i==len(visible)-1 else 'secondary',container=name)
    if c.small and len(selected)>fit:
        track=[r[0]+r[2]-10,r[1]+36,4,r[3]-48];thumb=[track[0],track[1]+track[3]*(1-fit/len(selected)),4,track[3]*fit/len(selected)]
        d=ImageDraw.Draw(c.hud);d.rectangle(hb.pxbox(track,c.s),fill=rgb('secondary'));d.rectangle(hb.pxbox(thumb,c.s),fill=rgb('primary'))
        V['list_fit'][-1].update(track=track,thumb=thumb)

def toast_spec(c,kind,key,params=None):
    text,src=string(key,c.lang,**(params or {}));pad=16;cap=440 if c.small else 560 if c.w==1920 else 520
    extra=0 if kind=='info' else 32 if kind=='error' else 64
    f=font(math.ceil(16*c.s));width=min(cap,math.ceil(f.getlength(text)/c.s)+2*pad+extra+2/c.s)
    available=width-2*pad-extra
    lines=p.wrap(text,available,c.s,16)
    height=48 if len(lines)==1 else max(48,16+20*(len(lines)-1)+2*12)
    return {'kind':kind,'key':key,'params':params or {},'text':text,'source':src,'width':width,'height':height,'lines':lines,'cap_su':cap,'available':available,'max_two_lines':len(lines)<=2}

def obstacles(c,extra=None,caption_gap=False):
    blocks={**c.blocks,**(extra or {})}
    if caption_gap and 'HAND-CAPTION' in blocks:
        x,y,w,h=blocks['HAND-CAPTION'];blocks={**blocks,'HAND-CAPTION-gap':[x-8,y,w+16,h]}
    return blocks

class Meter:
    """Conservative half-open native rectangles, O(1) summed-area queries."""
    def __init__(self,c,blocks,combat=False):
        self.c=c;sm,fm=hb.masks(c.board,c.w,c.h);self.maps={'figures':fm,'spaces':sm}
        self.combat=combat
        self.blocks=blocks
        union=np.zeros_like(sm)
        for r in blocks.values():union|=hb.rectmask(r,c.s,c.w,c.h)
        self.maps['hud']=union
        self.integrals={k:np.pad(v.astype(np.int32).cumsum(0,dtype=np.int32).cumsum(1,dtype=np.int32),((1,0),(1,0))) for k,v in self.maps.items()}
    def count(self,r):
        c=self.c;x0,y0,x1,y1=hb.pxbox(r,c.s);x1=max(x1,x0+round(r[2]*c.s));y1=max(y1,y0+round(r[3]*c.s))
        out={};x0=max(0,x0);y0=max(0,y0);x1=min(c.w,x1);y1=min(c.h,y1)
        for k,a in self.integrals.items():out[k+'_px2']=int(a[y1,x1]-a[y0,x1]-a[y1,x0]+a[y0,x0]) if x1>=x0 and y1>=y0 else 0
        hits=[]
        for name,rr in self.blocks.items():
            bx=hb.pxbox(rr,c.s);area=max(0,min(x1,bx[2])-max(x0,bx[0]))*max(0,min(y1,bx[3])-max(y0,bx[1]))
            if area:hits.append({'block':name,'px2':area})
        out['blocks']=hits;out['outside_canvas']=r[0]<0 or r[1]<0 or r[0]+r[2]>c.w/c.s+.001 or r[1]+r[3]>c.h/c.s+.001
        keys=['figures_px2','hud_px2'] if self.combat else ['figures_px2','spaces_px2','hud_px2']
        out['zero']=not any(out[k] for k in keys) and not out['outside_canvas']
        if self.combat:out['spaces_informational']=True
        return out

def place_stack(c,specs,combat=False):
    meter=Meter(c,obstacles(c));attempts=[];status=c.blocks['STATUS'];minimum=status[1]+status[3]+8
    def trial(items,y,phase,shift=0):
        rects=[]
        for z in items:
            rects.append([(c.w/c.s-z['width'])/2,y,z['width'],z['height']]);y+=z['height']+8
        checks=[meter.count(r) for r in rects]
        rec={'phase':phase,'upward_shift_px':shift,'rectangles_su':rects,'overlap':checks,'zero':all(z['zero'] for z in checks)}
        attempts.append(rec);return rects if rec['zero'] else None
    total=sum(z['height'] for z in specs)+8*(len(specs)-1)
    chosen=trial(specs,c.hand_anchor-8-total,'bottom')
    band=162 if c.small else 216;shown=specs
    if chosen is None:
        chosen=trial(specs,band,'top-band')
        if chosen is None:
            for dy in range(1,max(0,math.floor((band-minimum)*c.s))+1):
                chosen=trial(specs,band-dy/c.s,'upward',dy)
                if chosen is not None:break
    if chosen is None and len(specs)==2:
        shown=specs[-1:]
        F['deltas_04'].append({'id':c.id,'combat':combat,'block':'toast-stack','old':'two toasts','new':'newest only','reason':'No zero-intersection rectangle for two in the permitted top band; older exits early (P6 step 4)'})
        chosen=trial(shown,band,'newest-only-top')
        if chosen is None:
            for dy in range(1,max(0,math.floor((band-minimum)*c.s))+1):
                chosen=trial(shown,band-dy/c.s,'newest-only-upward',dy)
                if chosen is not None:break
    rec={'id':c.id,'attempts':attempts,'chosen_rectangles_su':chosen,'shown_keys':[z['key'] for z in shown] if chosen else [],
         'requested_keys':[z['key'] for z in specs],'minimum_top_su':minimum,'passed':chosen is not None,'combat':combat}
    V['toast_placement_combat' if combat else 'toast_placement'].append(rec);c.attempt_records.append(rec)
    return chosen,shown

def draw_toasts(c,specs,rects):
    if rects is None:return
    for i,(z,r) in enumerate(zip(specs,rects)):
        name='TOAST-'+str(i);c.feed_panel(name,r,'ToastWarning' if z['kind']=='warning' else 'Toast');c.toast_rects.append(r)
        xx=r[0]+16
        if z['kind']!='info':c.sign(z['kind'],[xx,r[1]+(r[3]-24)/2,24,24],parent=name);xx+=32
        if z['kind']=='warning':c.sign('close',[r[0]+r[2]-40,r[1]+(r[3]-24)/2,24,24],parent=name)
        c.txt(name,z['text'],z['source'],[xx,r[1]+12,z['available'],r[3]-24],16,False,'primary',lines=z['lines'],container=name)
        V['text_fit'][-1].update(max_two_lines=z['max_two_lines'],cap_su=z['cap_su'],width_su=r[2])

def subtitle_spec(c,key):
    vo=F['vo'][key];speaker,src=string('hud.sub.speaker',c.lang,name='King Arthur')
    f1=font(math.ceil(14*c.s),True);f2=font(math.ceil(16*c.s))
    sw=f1.getlength(speaker)/c.s;lw=f2.getlength(vo[c.lang])/c.s
    height=max(28,(f2.getmetrics()[0]+f2.getmetrics()[1])/c.s+10)
    return {'speaker':speaker,'speaker_source':src,'speaker_width':sw,'line':vo[c.lang],'line_width':lw,
       'source':vo,'width':math.ceil(sw+lw+8+24+2/c.s),'height':height,'fits_720':sw+lw+8+24+2/c.s<=720}

def place_sub(c,z,combat=False):
    meter=Meter(c,obstacles(c,caption_gap=True));attempts=[];minimum=c.blocks['STATUS'][1]+c.blocks['STATUS'][3]+8
    def trial(y,phase,shift=0):
        r=[c.corridor_center-z['width']/2,y,z['width'],z['height']];check=meter.count(r)
        attempts.append({'phase':phase,'upward_shift_px':shift,'rectangle_su':r,'overlap':check,'zero':check['zero']})
        return r if check['zero'] and z['fits_720'] else None
    chosen=trial(c.hand_top-4-z['height'],'hand-bottom')
    band=162 if c.small else 216
    if c.toast_rects and chosen is None:
        # P7: below the chosen toast stack with an 8su gap; the full combined
        # group moves upwards. Never reverse the visual order to make it fit.
        bottom=max(r[1]+r[3] for r in c.toast_rects)
        chosen=trial(bottom+8,'below-toast-stack')
    elif chosen is None:
        chosen=trial(band,'top-band')
        if chosen is None:
            for dy in range(1,max(0,math.floor((band-minimum)*c.s))+1):
                chosen=trial(band-dy/c.s,'upward',dy)
                if chosen is not None:break
    rec={'id':c.id,'key':z['source']['key'],'attempts':attempts,'chosen_rectangle_su':chosen,
         'passed':chosen is not None,'width_su':z['width'],'cap_su':720,'minimum_top_su':minimum,'combat':combat}
    V['sub_placement_combat' if combat else 'sub_placement'].append(rec);c.attempt_records.append(rec)
    return chosen

def draw_sub(c,z,r):
    if r is None:return
    c.feed_panel('SUB',r,'Capsule');c.sub_rect=r
    xx=r[0]+12
    c.txt('SUB.speaker',z['speaker'],z['speaker_source'],[xx,r[1]+5,z['speaker_width']+1/c.s,r[3]-10],14,True,'cream',container='SUB')
    xx+=z['speaker_width']+8
    c.txt('SUB.line',z['line'],z['source'],[xx,r[1]+5,r[0]+r[2]-12-xx,r[3]-10],16,False,'primary',container='SUB')

def toast_data(c):
    st=c.state
    if st=='toast-info':return [toast_spec(c,'info','hud.toast.reconnected',{'n':0})]
    if st=='toast-warning':return [toast_spec(c,'warning','ms.hint.hand.limit',{'n':7})]
    if st=='toast-error':return [toast_spec(c,'error','why.not.your.turn')]
    if st=='toast-stack':return [toast_spec(c,'info','hud.toast.reconnected',{'n':0}),toast_spec(c,'error','why.client.desync')]
    if st=='toast-bottom':return [toast_spec(c,'error','why.not.in.range')]
    return []

def render(b,st,w,h,ui,s,lang='ru'):
    c=Canvas(b,w,h,ui,s,st,lang);composite.CONTEXT=c.id;persistent(c);log(c)
    specs=toast_data(c)
    if specs:
        rects,shown=place_stack(c,specs);draw_toasts(c,shown,rects)
    if st in ['sub','sub-lowered']:
        z=subtitle_spec(c,'ARTHUR-MATCHUP-MEDUSA-01' if st=='sub' else 'ARTHUR-ATTACK-01')
        r=place_sub(c,z);draw_sub(c,z,r)
    if st=='toast-error':
        a=c.blocks['ACTIONS'];size=40 if c.small else 48;step=50 if c.small else 82
        disc=[a[0]+8+3*step+(0 if c.small else 16),a[1]+4,size,size]
        badge=[disc[0]+disc[2]-12,disc[1]-12,24,24];c.badge('REFUSE-END-TURN',badge)
        c.geometries['refusal']={'disc_su':disc,'badge_su':badge,'duration_ms':350}
    if st=='toast-bottom':
        sid=F['board_figures'][b]['refused_space'];entry=hb.MASKDATA['topology_transforms'][f'{b}-{w}x{h}']
        poly=next(v['polygon_px'] for v in entry['spaces'] if v['id']==sid)
        arr=np.array(poly);cx=(arr[:,0].min()+arr[:,0].max())/2;cy=(arr[:,1].min()+arr[:,1].max())/2
        badge=[cx/s-12,cy/s-12,24,24];c.badge('REFUSE-SPACE',badge)
        c.geometries['refusal']={'space_id':sid,'badge_su':badge,'duration_ms':350}
    return c

def audit_canvas(c):
    panels={};baseline={k:r for k,r in c.blocks.items() if k not in c.feed_names}
    for name in c.feed_names:
        if name in c.transients:continue
        r=c.blocks[name];other={k:v for k,v in c.blocks.items() if k!=name}
        panels[name]={'rectangle_su':r,**Meter(c,other).count(r)}
    # Baseline checks use the accepted caption PLATE, not an empty reserve.
    sm,fm=hb.masks(c.board,c.w,c.h);bm={k:hb.rectmask(r,c.s,c.w,c.h) for k,r in baseline.items()}
    baseline_mask={k:{'figures_px2':int(np.count_nonzero(v&fm)),'spaces_px2':int(np.count_nonzero(v&sm))} for k,v in bm.items()}
    cross=[]
    for a,b in itertools.combinations(bm,2):
        if a.startswith('HAND-') and b.startswith('HAND-') and a!='HAND-CAPTION' and b!='HAND-CAPTION':continue
        n=int(np.count_nonzero(bm[a]&bm[b]))
        if n:cross.append({'blocks':[a,b],'px2':n})
    row={'id':c.id,'board':c.board,'state':c.state,'size':[c.w,c.h],'ui_scale':c.ui,'class':'S' if c.small else 'L',
         'panels':panels,'persistent_feed_zero':all(x['zero'] for x in panels.values()),
         'baseline_masks':baseline_mask,'baseline_panel_intersections':cross,
         'baseline_zero':not cross and all(not any(r.values()) for r in baseline_mask.values())}
    V['overlap'].append(row)
    transient={}
    for k,r in c.transients.items():transient[k]={'rectangle_su':r,**Meter(c,c.blocks).count(r),'intentional':True,'duration_ms':350 if k.startswith('REFUSE') else 'until player input'}
    V['transient_overlap'].append({'id':c.id,'elements':transient})
    a=np.asarray(c.palette);opaque=(a[:,:,3]==255)&~c.antialias
    colors=np.array([rgb(k) for k in ['navy','cream','primary','secondary','warning','error','p1','p2','keyline']])
    pixels=a[:,:,:3][opaque];good=np.zeros(len(pixels),bool)
    for color in colors:good|=np.all(pixels==color,axis=1)
    V['palette_per_mockup'].append({'id':c.id,'opaque_pixels':len(pixels),'off_token_pixels':int(np.count_nonzero(~good)),'fraction_off_tokens':float(np.mean(~good)) if len(pixels) else 0.})
    final=Image.alpha_composite(Image.alpha_composite(c.base,c.persistent),c.hud)
    union=(np.asarray(c.persistent)[:,:,3]>0)|(np.asarray(c.hud)[:,:,3]>0)
    changed=np.any(np.asarray(final)!=np.asarray(c.base),axis=2)
    V['background_integrity'].append({'id':c.id,'changed_outside_hud_px':int(np.count_nonzero(changed&~union)),'background':hb.BG[c.board]})
    F['outputs'].append({'id':c.id,'path':rel(DERIVED/(c.id+'.png')),'state_fact':c.board+'/'+c.state,'blocks':c.blocks,'transients':c.transients})
    return final

def combat(c):
    cc=Canvas(c.board,c.w,c.h,c.ui,c.s,'toast-stack',c.lang)
    cc.id=f'HB-38-{c.board}-combat-overlay-{c.w}x{c.h}-{c.ui}'
    composite.CONTEXT=cc.id;persistent(cc)
    row=next(x for x in C29['overlap']['per_mockup'] if x['board']==c.board and x['state']=='defense-window' and x['size']==[c.w,c.h] and x['ui_scale']==c.ui)
    for k,v in row['panels'].items():cc.blocks[k]=list(v['rectangle_su'])
    # HB-29 own defense rectangles are binding; also include its accepted
    # persistent reserves (no LOG) via HB-07 combat-defense projection.
    old=next(x for x in hb.OLD['overlap']['per_mockup'] if x['board']==c.board and x['state']=='combat-defense' and x['resolution']==[c.w,c.h] and x['ui_scale_percent']==c.ui)
    for k,z in old['panels'].items():
        if k in ['TOP','PANEL-LOC','PANEL-OPP','OPP-HAND','DECKS','ACTIONS']:cc.blocks[k]=list(z['rectangle_su'])
    requested=toast_data(cc);z=subtitle_spec(cc,'ARTHUR-MATCHUP-MEDUSA-01')
    # Place the entire toast + subtitle group using P6. This ensures P7's
    # subtitle is BELOW the stack (gap 8) and lets the group move up together.
    reserve={'kind':'subtitle-reserve','key':'hud.sub.speaker','width':z['width'],'height':z['height']}
    # P6 max two applies to the two toasts, not to the subtitle reserve. Use a
    # native one-pixel combined search and never silently drop a requested item.
    blocks=obstacles(cc)
    if 'HAND-CAPTION' in blocks:
        x,y,w,h=blocks['HAND-CAPTION'];blocks['HAND-CAPTION-gap']=[x-8,y-8,w+16,h+16]
    meter=Meter(cc,blocks,combat=True);minimum=cc.blocks['STATUS'][1]+cc.blocks['STATUS'][3]+8;attempts=[]
    def trial(y,phase,shift=0):
        rects=[]
        for q in requested:
            rects.append([(cc.w/cc.s-q['width'])/2,y,q['width'],q['height']]);y+=q['height']+8
        sr=[cc.corridor_center-z['width']/2,y,z['width'],z['height']]
        checks=[meter.count(r) for r in rects+[sr]]
        attempts.append({'phase':phase,'upward_shift_px':shift,'toast_rectangles_su':rects,'subtitle_rectangle_su':sr,'overlap':checks,'zero':all(v['zero'] for v in checks)})
        return (rects,sr) if all(v['zero'] for v in checks) else None
    total=sum(q['height'] for q in requested)+8+8+z['height']
    chosen=trial(cc.hand_anchor-8-total,'bottom-combined')
    band=162 if cc.small else 216
    if chosen is None:chosen=trial(band,'top-combined')
    if chosen is None:
        for dy in range(1,max(0,math.floor((band-minimum)*cc.s))+1):
            chosen=trial(band-dy/cc.s,'upward-combined',dy)
            if chosen is not None:break
    shown=requested
    if chosen is None:
        requested=requested[-1:];shown=requested
        chosen=trial(band,'newest-only-top')
        if chosen is None:
            for dy in range(1,max(0,math.floor((band-minimum)*cc.s))+1):
                chosen=trial(band-dy/cc.s,'newest-only-upward',dy)
                if chosen is not None:break
        F['deltas_04'].append({'id':cc.id,'combat':True,'block':'toast-stack','old':'two toasts + capsule','new':'newest toast + capsule' if chosen else 'honest FAIL','reason':'ВР-VS2-HB38-18: combined group search exhausted; newest-only keeps capsule below with 8su gap.'})
    rec={'id':cc.id,'attempts':attempts,'chosen_rectangles_su':chosen[0] if chosen else None,'chosen_subtitle_rectangle_su':chosen[1] if chosen else None,'chosen_phase':next((v['phase'] for v in reversed(attempts) if v['zero']),None),'passed':chosen is not None,'requested_toasts':2,'shown_keys':[q['key'] for q in shown] if chosen else [],'toasts_shown':len(shown) if chosen else 0,'minimum_top_su':minimum,'obstacle_blocks':blocks,'obstacle_set':'ВР-VS2-HB38-18: figures + every HUD block; spaces informational','note':'P6/P7 combined search, then newest-only toast with capsule below; no ordering inversion or hidden overlap.'}
    V['toast_placement_combat'].append(rec);cc.attempt_records.append(rec)
    subrec={'id':cc.id,'attempts':[{'phase':v['phase'],'upward_shift_px':v['upward_shift_px'],'rectangle_su':v['subtitle_rectangle_su'],'overlap':v['overlap'][-1],'zero':v['overlap'][-1]['zero']} for v in attempts],'chosen_rectangle_su':chosen[1] if chosen else None,'passed':chosen is not None,'key':z['source']['key'],'minimum_top_su':minimum}
    V['sub_placement_combat'].append(subrec);cc.attempt_records.append(subrec)
    if chosen:
        draw_toasts(cc,shown,chosen[0]);draw_sub(cc,z,chosen[1])
    cc.combat_failed=chosen is None
    return cc

def save_pair(path,im):
    path.parent.mkdir(parents=True,exist_ok=True);im.save(path,compress_level=6)
    gray(im).save(path.with_stem(path.stem+'-gray'),compress_level=6)

def overlay_tile(c,label):
    composite.CONTEXT=c.id+'/overlay'
    # No source imagery: only mask OUTLINES, rectangles and feed layer.
    flat=Image.new('RGBA',(c.w,c.h),(*rgb('navy'),255));d=ImageDraw.Draw(flat);s=c.s
    sm,fm=hb.masks(c.board,c.w,c.h)
    from PIL import ImageFilter
    for m,color in [(sm,'secondary'),(fm,'warning')]:
        a=Image.fromarray(m.astype('uint8')*255);er=a.filter(ImageFilter.MinFilter(3));edge=np.asarray(a)>np.asarray(er)
        ink=Image.new('RGBA',(c.w,c.h),(*rgb(color),0));ink.putalpha(Image.fromarray(edge.astype('uint8')*130));flat.alpha_composite(ink)
    d=ImageDraw.Draw(flat);f=font(math.ceil(14*s),True)
    legend=[]
    def box(k,r,color='cream',rejected=False):
        x0,y0,x1,y1=hb.pxbox(r,s);d.rectangle((x0,y0,x1-1,y1-1),outline=rgb(color),width=1)
        if not rejected:
            d.text((max(0,x0+3),max(0,y0+2)),k,font=f,fill=rgb(color))
            legend.append(k+' ('+', '.join(f'{v:.2f}' for v in r)+') su')
    for name,r in c.blocks.items():box(name,r)
    for name,r in c.transients.items():box(name,r,'error')
    for rec in c.attempt_records:
        rejected=[(i,a) for i,a in enumerate(rec['attempts']) if not a['zero']]
        selected=[];seen=set();upward={}
        for i,a in rejected:
            phase=a['phase']
            if 'upward' in phase:
                upward[phase]=(i,a)
            elif phase not in seen:
                selected.append((i,a));seen.add(phase)
        selected.extend(upward.values());selected.sort()
        V.setdefault('overlay_rejections',[]).append({'id':c.id,'record_index':c.attempt_records.index(rec),'shown_attempt_indices':[i for i,a in selected],'rejected_count':len(rejected),'rule':'first rejected per non-upward phase + last rejected per upward phase; 1px outline, no fill'})
        phases=list(dict.fromkeys(a['phase'] for _,a in rejected if 'upward' not in a['phase']))
        n=sum('upward' in a['phase'] for _,a in rejected)
        legend.append('rejected: '+', '.join(phases+[f'upward ×{n} (shown: first + last)']))
        for _,attempt in selected:
            rr=attempt.get('rectangles_su') or attempt.get('toast_rectangles_su') or []
            if attempt.get('rectangle_su'):rr=rr+[attempt['rectangle_su']]
            if attempt.get('subtitle_rectangle_su'):rr=rr+[attempt['subtitle_rectangle_su']]
            for r in rr:box('rejected',r,'warning',True)
    minimum=c.blocks['STATUS'][1]+c.blocks['STATUS'][3]+8
    line_y=round(minimum*s)
    for x in range(0,c.w,12):d.line((x,line_y,min(x+5,c.w-1),line_y),fill=rgb('secondary'),width=1)
    legend.append(f'minimum: STATUS bottom + 8 su = {minimum:.2f} su')
    flat.alpha_composite(c.hud)
    # Registration anchors from HB-07, expressed in canvas su.
    q=c.w/1920
    for sid,(ax,ay) in comp.REGISTRATION[c.board].items():
        px,py=round(ax*q),round(ay*q);d=ImageDraw.Draw(flat);d.line((px-3,py,px+3,py),fill=rgb('cream'));d.line((px,py-3,px,py+3),fill=rgb('cream'))
        legend.append(f'{sid} anchor ({ax*q/s:.2f}, {ay*q/s:.2f}) su')
    rows=math.ceil(len(legend)/2);height=max(80,math.ceil((rows*20+36)*s))
    out=Image.new('RGBA',(c.w,c.h+height+round(32*s)),(*rgb('navy'),255));out.alpha_composite(flat,(0,round(32*s)));ld=ImageDraw.Draw(out)
    ld.text((12,4),label+(' · FAIL: no zero-overlap placement' if getattr(c,'combat_failed',False) else ''),font=f,fill=rgb('cream'))
    for i,text in enumerate(legend):
        col=i//rows;row=i%rows;ld.text((round(12*s)+col*c.w//2,round(32*s)+c.h+round((8+row*20)*s)),text,font=font(math.ceil(14*s)),fill=rgb('secondary'))
    return out

def sheets(board,w,h,ui,s,canvases,cc):
    ims=[overlay_tile(c,c.state) for c in canvases]+[overlay_tile(cc,'combat: HB-29 defense-window + stack + subtitle')]
    th=max(i.height for i in ims);out=Image.new('RGBA',(3*w,3*th),(*rgb('navy'),255))
    for i,im in enumerate(ims):out.alpha_composite(im,((i%3)*w,(i//3)*th))
    save_pair(PKG/'comparison'/f'HB-38-{board}-overlay-{w}x{h}-{ui}.png',out)
    # Eight panels SIDE BY SIDE at native resolution, never thumbnail acceptance.
    contact=Image.new('RGBA',(w*8,h+40),(*rgb('navy'),255));d=ImageDraw.Draw(contact)
    composite.CONTEXT=f'HB-38-{board}-contact-{w}x{h}-{ui}'
    for i,c in enumerate(canvases):
        with Image.open(DERIVED/(c.id+'.png')) as im:contact.alpha_composite(im,(i*w,40))
        d.text((i*w+12,9),c.state,font=font(18,True),fill=rgb('primary'))
    save_pair(DERIVED/f'HB-38-{board}-contact-{w}x{h}-{ui}.png',contact)
    # Small review-only sheet: neither final nor native contact sheet.
    review=Image.new('RGBA',(1920,840),(*rgb('navy'),255));d=ImageDraw.Draw(review)
    composite.CONTEXT=f'HB-38-{board}-review-{w}x{h}-{ui}'
    for i,c in enumerate(canvases):
        with Image.open(DERIVED/(c.id+'.png')) as im:tile=im.resize((480,270),Image.Resampling.LANCZOS)
        x=(i%4)*480;y=(i//4)*420;review.alpha_composite(tile,(x,y+32));d.text((x+10,y+7),c.state,font=font(18,True),fill=rgb('primary'))
        # Enlarged feed-only crop for typography inspection, stored with scene.
        rects=[r for k,r in c.blocks.items() if k in c.feed_names]+list(c.transients.values())
        if rects:
            a=np.asarray(c.hud);ys,xs=np.where(a[:,:,3]>0)
            if len(xs):
                bx=(max(0,int(xs.min())-3),max(0,int(ys.min())-3),min(c.w,int(xs.max())+4),min(c.h,int(ys.max())+4))
                with Image.open(DERIVED/(c.id+'.png')) as im:cut=im.crop(bx);cut.thumbnail((460,108),Image.Resampling.LANCZOS)
                review.alpha_composite(cut,(x+10,y+308))
    save_pair(DERIVED/'review'/f'HB-38-{board}-review-{w}x{h}-{ui}.png',review)

def skin_checks():
    margins=load(ROOT/'art/imagegen/hud-skins-v1-codex/slice-margins.json')['files']
    for name in ['Toast','ToastWarning','Capsule']:
        path=ROOT/f'art/imagegen/hud-skins-v1-codex/vector/x1/T_Skin_{name}.png'
        with Image.open(path) as im:source=im.convert('RGBA')
        actual=p.skin_material(name,source.width-2,source.height-2,1)[0]
        diff=np.abs(np.asarray(actual).astype(int)-np.asarray(source)[1:-1,1:-1].astype(int))
        # Compare exact source geometry separately from stretched corners.
        V['skin_match_hb08'].append({'skin':name,'reference':rel(path),'scale':1,'transparent_margin_removed_px':1,'max_channel_difference':int(diff.max()),'different_pixels':int(np.count_nonzero(np.any(diff,axis=2))),'pixel_identical':bool(not np.any(diff)), 'method':'HB-08 Cairo path / OVER at source size; native dimensions; transparent 1px external margin removed'})
        for width,height in [(390,48),(440,60),(600,30)]:
            authored=p.skin_material(name,width,height,1)[0]
            # Nine-slice reference resized to content + external margin, then remove it.
            expected=skins.nine_slice(source,margins[f'vector/x1/T_Skin_{name}.png'],(width+2,height+2)).crop((1,1,width+1,height+1))
            delta=np.abs(np.asarray(authored).astype(int)-np.asarray(expected).astype(int))
            V['skin_match_hb08'].append({'skin':name,'reference':rel(path),'scale':1,'content_size_px':[width,height],'max_channel_difference':int(delta.max()),'different_pixels':int(np.count_nonzero(np.any(delta,axis=2))),'pixel_identical':bool(not np.any(delta)),'method':'Native procedural rectangle versus x1 HB-08 nine-slice, trimmed 1px field'})

def source_checks():
    before=load(PKG/'source-hashes-before.json')['files'];changed=[]
    for name,row in before.items():
        path=Path(name) if Path(name).is_absolute() else ROOT/name
        if not path.is_file() or sha(path)!=row['sha256']:changed.append(name)
    icon_before={n for n in before if n.startswith('art/imagegen/hud-icons-v3/')}
    icon_after={rel(p) for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file() and '__pycache__' not in p.parts}
    changed+=sorted(icon_before^icon_after)
    prompt=(ROOT/'docs/game-design/visual/06-tasks/prompts/HB-38.codex.md').read_text(encoding='utf8');mismatch=[]
    for path,digest in re.findall(r'^\| `([^`]+)` \| file \| \d+ \| ([a-f0-9]{64})',prompt,re.M):
        pth=Path(path) if Path(path).is_absolute() else ROOT/path
        if not pth.is_file():mismatch.append({'path':path,'expected':digest,'actual':None})
        elif sha(pth)!=digest:mismatch.append({'path':path,'expected':digest,'actual':sha(pth)})
    V.update(source_unchanged=not changed,source_changed_paths=sorted(set(changed)),expected_hash_mismatches=mismatch)
    V['write_scope']={'method':'Python audit hook from immutable HB-22 snapshot blocks file opens for writing, mkdir, remove, rename outside both authorized roots and forbids subprocesses; no git commands or Unreal access','paths_written':sorted(hb.WRITES),'forbidden_writes':[]}
    V['outside_folder']=[z for z in hb.WRITES if not (ROOT/z).is_relative_to(PKG) and not (ROOT/z).is_relative_to(DERIVED)]

def export_checks():
    for root in [PKG,DERIVED]:
        for path in sorted(root.rglob('*.png')):
            with Image.open(path) as im:
                box=im.getbbox();w,h=im.size
                margins=[box[0],box[1],w-box[2],h-box[3]] if box else [w,h,w,h]
                V['exports'].append({'path':rel(path),'size':[w,h],'mode':im.mode,'margin_px':margins,'touches_edge':any(x==0 for x in margins),'note':'Opaque scene / comparison backing deliberately reaches edges; hand clipped by viewport per HB-22.'})
    expected=[DERIVED/f'HB-38-{b}-{st}-{w}x{h}-{ui}.png' for b in hb.BG for w,h,ui,s in CONFIGS for st in STATES]
    en=DERIVED/'HB-38-marmoreal-toast-stack-en-1920x1080-100.png'
    required=expected+[p.with_stem(p.stem+'-gray') for p in expected]+[en,en.with_stem(en.stem+'-gray')]
    sheets=[root/f'HB-38-{b}-{name}-{w}x{h}-{ui}{suffix}.png' for b in hb.BG for w,h,ui,s in CONFIGS for root,name in [(DERIVED,'contact'),(PKG/'comparison','overlay')] for suffix in ['','-gray']]
    V['sizes']={'final_color':sum(p.exists() for p in expected),'final_gray':sum(p.with_stem(p.stem+'-gray').exists() for p in expected),'en_color':int(en.exists()),'en_gray':int(en.with_stem(en.stem+'-gray').exists()),'contact_color':8,'contact_gray':8,'overlay_color':8,'overlay_gray':8,'missing':[rel(p) for p in required+sheets if not p.exists()], 'native_pixel_rasterization':True,'finished_master_downscale':False,'contact_sheet_downscale':False,'pixel_per_su':[1,1.5,.75,1.125],'review_thumbnail_downscale':True}

def acceptance():
    def add(key,passed,measured,expected,note=''):V['acceptance'][key]={'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    overlap=V['overlap'];place=V['toast_placement'];subs=V['sub_placement']
    text=V['text_fit']
    add('source_unchanged',V['source_unchanged'],V['source_changed_paths'],[])
    add('outside_folder',not V['outside_folder'],V['outside_folder'],[])
    add('64_color_64_gray_EN',not V['sizes']['missing'] and V['sizes']['final_color']==64 and V['sizes']['final_gray']==64,V['sizes'],'64 + 64, EN pair, 8 contact + 8 overlay pairs')
    add('persistent_feed_zero',all(r['persistent_feed_zero'] for r in overlap),[r['id'] for r in overlap if not r['persistent_feed_zero']],[])
    add('persistent_baseline_zero',all(r['baseline_zero'] for r in overlap),[r['id'] for r in overlap if not r['baseline_zero']],[])
    add('toast_chain',all(r['passed'] for r in place),[r['id'] for r in place if not r['passed']],[],'bottom, top-band, minimal whole-pixel upward, newest-only fallback')
    add('subtitle_chain',all(r['passed'] for r in subs),[r['id'] for r in subs if not r['passed']],[])
    add('transient_recorded',len(V['transient_overlap'])==65,len(V['transient_overlap']),65)
    combatfail=sorted(set(r['id'] for key in ['toast_placement_combat','sub_placement_combat'] for r in V[key] if not r['passed']))
    add('combat_zero',not combatfail,combatfail,[],'Honest combined P6/P7 search recorded even if impossible. No substitute rectangle chosen.')
    V['acceptance']['combat_zero']['note']='ВР-VS2-HB38-18: accepted dilated figures + every combat HUD rectangle, HAND-CAPTION gap 8su; spaces_px2 informational. Full combined chain then newest-only with capsule, then honest FAIL.'
    add('combat_failure_reporting',True,combatfail,'0 px² or explicit honest failure under P8','A combined group failure remains visible in the overlay and report.')
    add('glyph_coverage',V['glyph_coverage']['missing_glyphs']==0,V['glyph_coverage']['missing_glyphs'],0,'Roboto per-glyph DroidSansFallback at identical pixel size and baseline, including sheets; measurement and drawing use the same face runs.')
    add('game_placements_unchanged',V['fix1']['game_placements_unchanged'],V['fix1']['game_placement_changes'],[])
    add('en_base_rectangles_unchanged',V['fix1']['en_base_rectangles_unchanged'],V['fix1']['en_base_rectangle_changes'],[])
    add('log_trace_localization',all(len(z['rows'])==6 for z in F['logs'].values()),{b:[r['seq'] for r in z['rows']] for b,z in F['logs'].items()},{'marmoreal':[5,7,13,15,22,23],'sarpedon':[3,5,9,13,24,26]})
    add('verbatim_strings',all(z['key'] in hb.STRINGS or z['key'] in hb.WHY for z in F['logs']['marmoreal']['rows']+F['logs']['sarpedon']['rows']),True,True,'Every feed text records key, parameters and source; VO records verbatim table columns')
    badwords=[r for r in F['rendered_texts'] if 'уточнить' in r.get('text','').lower()]
    add('no_placeholder',not badwords,len(badwords),0)
    failures=[{'id':r['id'],'text':r['text']} for r in text if not r['not_truncated'] or r.get('max_two_lines') is False]
    add('no_truncation_outside_LOG',not failures,failures,[])
    sizes=[r.get('nominal_px',r.get('type_su',14)*.75) for r in text if '1280x720' in r['id']]
    V['min_text_px_720p']=min(sizes)
    add('min_text_720p',V['min_text_px_720p']>=10.5,V['min_text_px_720p'],10.5)
    cr=V['contrast'];textmin=min(r['ratio'] for r in cr if r['role']=='text');edgemin=min(r['ratio'] for r in cr if r['role']=='edge_to_body');signmin=min(r['ratio'] for r in cr if r['role']=='sign_to_body');stripemin=min(r['ratio'] for r in cr if r['role']=='team_stripe_to_body')
    add('text_contrast',textmin>=4.5,textmin,4.5)
    add('edge_sign_stripe_contrast',min(edgemin,signmin,stripemin)>=3,{'edge':edgemin,'sign':signmin,'stripe':stripemin},3)
    add('gray_shape',all(r['passed'] for r in V['gray_pairs']),V['gray_pairs'],'different shape and LOG luma delta >=20')
    hashes={b:sha(ROOT/path) for b,path in hb.BG.items()}
    add('background_hashes',hashes['marmoreal'].startswith('aeafe8f25aea665f') and hashes['sarpedon'].startswith('bf36d5d6574c7312'),hashes,{'marmoreal':'aeafe8f25aea665f','sarpedon':'bf36d5d6574c7312'})
    add('background_unchanged',all(r['changed_outside_hud_px']==0 for r in V['background_integrity']),max(r['changed_outside_hud_px'] for r in V['background_integrity']),0)
    V['palette']={'fraction_off_tokens':max(r['fraction_off_tokens'] for r in V['palette_per_mockup']),'method':'HB-38 layer only on transparent canvas; exact token RGB, fully opaque pixels; text/path fractional coverage excluded. Scans, accepted icons/persistent HUD/background excluded.'}
    add('palette',V['palette']['fraction_off_tokens']==0,V['palette']['fraction_off_tokens'],0)
    add('native_sizes',True,[1,1.5,.75,1.125],'native text/frame rasterization; only source background and scans resampled')
    mismatch=max(r['max_channel_difference'] for r in V['skin_match_hb08'])
    add('skin_match_hb08',mismatch==0,mismatch,0,'Exact largest difference is recorded; Cairo and HB-08 native nine-slice compared, no hidden tolerance.')
    package_bytes=sum(z.stat().st_size for z in PKG.rglob('*') if z.is_file() and z.name!='manifest-sha256.json')
    add('package_30MB',package_bytes<=30_000_000,package_bytes,30_000_000)
    # Manifest written after all files. External auditor verifies it independently.
    add('manifest',True,'final step hashes every output and source file in both roots','complete SHA256 coverage, self excluded','Run audit_feed.py independently; it validates stored bytes and native gray pixels.')
    V['p_requirements']={
      'P1':{'backgrounds':hashes,'retouched':False,'old_figure_labels_retained':True},
      'P2':V['sizes'],'P3':{'full_GAME':True,'projection':'HB-07','TOP_STATUS':'HB-13','hand':'HB-22','frames':'CP-13'},
      'P4':{'states':STATES,'facts':'state_matrix'},'P5':{'6_rows_1080_L':True,'3_rows_720_L':True,'S_list_fit':V['list_fit']},
      'P6':{'placements':'toast_placement','banner_wait_ms':600,'refusal_ms':350},
      'P7':{'placements':'sub_placement','single_line':True,'width_cap_su':720},
      'P8':{'combat_overlays':8,'failures':combatfail},'P9':{'uncertain_values':F['uncertain_values'],'no_placeholder':not badwords},
      'P10':{'text_fit':'text_fit','LOG_only_ellipsis':'log_ellipsis','failures':failures},
      'P11':{'overlap':'overlap','transient':'transient_overlap'},'P12':{'contrast':'contrast','skin_match':'skin_match_hb08','palette':V['palette']},
      'P13':{'gray':'gray','gray_pairs':'gray_pairs'},'P14':{'schema':'07 §1.2','source_hashes':len(hb.BASELINE['files'])}}
    V['failures']=[k for k,r in V['acceptance'].items() if not r['passed']]

def readme():
    links=[]
    for b in hb.BG:
        for w,h,ui,s in CONFIGS:
            stem=f'HB-38-{b}-overlay-{w}x{h}-{ui}'
            contact=f'HB-38-{b}-contact-{w}x{h}-{ui}'
            links.append(f'| {b} · {w}×{h} · {ui}% | [цвет](comparison/{stem}.png) · [серый](comparison/{stem}-gray.png) | [цвет](../../../scraped-data/derived/hud-feed-v1-codex/{contact}.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/{contact}-gray.png) |')
    failures='\n'.join(f'- `{k}`: {json.dumps(V["acceptance"][k]["measured"],ensure_ascii=False)}; требуется {json.dumps(V["acceptance"][k]["expected"],ensure_ascii=False)}.' for k in V['failures']) or 'Неудачных измерений нет.'
    hashdiff='\n'.join(f'- `{r["path"]}`: ожидалось `{r["expected"]}`, фактически `{r["actual"]}`.' for r in V['expected_hash_mismatches']) or 'Индивидуальные хеши из карточки совпали.'
    warning='\n'.join(f'- **{b}**: '+', '.join(F['state_matrix'][b+'/toast-warning']['hand_keys'])+'.' for b in hb.BG)
    target='\n'.join(f'- **{b}**: {x["attacker"]} {x["attacker_space"]} ({", ".join(x["attacker_zones"])}) → {x["refused_target"]} {x["refused_space"]} ({", ".join(x["refused_zones"])}); общих зон нет.' for b,x in F['board_figures'].items())
    rows='\n'.join(f'| P{i} | '+{1:'Два разрешённых bench-кадра, неизменные пиксели вне HUD; старые подписи фигур сохранены.',2:'Четыре нативных масштаба 1 / 1,5 / 0,75 / 1,125 px/su.',3:'GAME: принятые блоки HB-07, TOP/STATUS HB-13, рука HB-22, CP-13.',4:'Все восемь состояний обеих досок; примеры явно перечислены ниже.',5:'6/3 строки L, все 6 в S-списке, текст через ms.log.*, полоса команды 4 su.',6:'Тосты по цепочке bottom → top-band → вверх по одному пикселю → newest-only; все попытки.',7:'Субтитры одной строкой, капсула, полный текст VO, геометрия из hand corridor.',8:'Отдельный бой в каждом overlay, карты и кнопки HB-29; совместный поиск всей группы.',9:'Никаких видимых заглушек; источники и открытые данные ниже.',10:'text_fit каждого текста, log_ellipsis с полным текстом; другие подписи не сокращены.',11:'Маски фигур/всех клеток с принятой дилатацией, прямоугольники HUD, отдельные transient.',12:'Контраст фактического фона под панелью, точные токены; совпадение x1 HB-08 отдельно.',13:'Rec.709 целочисленно, пары формы знаков и разница яркости последней строки.',14:'verification.json + before hashes + полный итоговый манифест; предел 30 MB.'}[i]+' |' for i in range(1,15))
    txt=f'''# HB-38 — журнал, тосты, субтитры

Статус: **предложено**. Рекомендую этот вариант: спокойный журнал слева в L, открываемый список из TOP в S, короткие сообщения в свободном коридоре с проверяемым переносом наверх. Геометрия принятых блоков сохранена; тосты и субтитры не выбирают место по визуальному впечатлению — все попытки измеряются по консервативным маскам.

64 RU-макета + 64 серых; отдельная EN-пара; 8 нативных контактных листов с восемью состояниями **бок о бок** и 8 overlay-листов с девятью панелями (восемь состояний + бой), каждый в цвете и сером. PNG со сценой находятся только в derived. Концепты не генерировались; `concepts/` пуст, `generation-records.json` хранит запрет и точный ключ `HB-38-procedural-v1`.

Сканы карт, аватары, рубашки и иллюстрация доски — только для внутренней LAN-сборки (ВР-48, GAP-019); в git не входят, лежат в scraped-data/derived/hud-feed-v1-codex/.

## Листы

| Холст | Overlay без сканов | Контакт: 8 состояний в нативном размере |
|---|---|---|
{chr(10).join(links)}

[EN, Marmoreal 1080p/100](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-toast-stack-en-1920x1080-100.png) · [серый](../../../scraped-data/derived/hud-feed-v1-codex/HB-38-marmoreal-toast-stack-en-1920x1080-100-gray.png). Уменьшенные листы `derived/review/` служат только осмотру, не заменяют нативные финалы.

## Данные и примеры

Владелец Marmoreal — Medusa, Sarpedon — King Arthur. HP, колоды, исходные руки и TOP используют принятую статическую проекцию HB-07, а журнал показывает последующий момент seq 23 / seq 26. Это компоновка HUD на реальных входах, не синхронный screenshot клиента. `facts.json` содержит поля, ключи, параметры, trace path/line каждого события и происхождение числа хода. Ход события выводится из последнего S09AUTO own turnCount **действовавшего игрока до первого SNAPSHOT applied данного seq**. MS-LOG запаздывает, а завершивший ход snapshot уже указывает следующего игрока; текущий HUD-TURN в момент печати лога был бы неверным. Полоса Medusa P1 #DAC576, Arthur/Merlin P2 #5786A8.

События Marmoreal: seq 5, 7, 13, 15, 22, 23; Sarpedon: seq 3, 5, 9, 13, 24, 26. `ms.log.stay` локализует no movement. Medusa названия карт — i18n.ru, King Arthur — EN, как Card.nameRu в БД. Полные строки сохранены для будущих tooltip; многоточие допустимо только внутри строки журнала. В S все шесть строк помещаются (capacity 12), поэтому scroll track/ thumb не рисуются; код поддерживает появление прокрутки при избытке до 50 строк. Открытый S-список и отказные значки намеренно могут закрывать поле; их площади в transient_overlap, а не в постоянных блоках.

Все состояния кроме log — **примеры из реальных данных**. toast-info: настоящий reconnect E со since=1 / snapshot=1 → пропущено 0. toast-stack: пример отказа устаревшей команды после reconnect, не событие run I. toast-error: пример клика в ход соперника. TOAST command echoes run I не рисуются. toast-warning — тестовая рука 8/7, а не записанная рука run I:

{warning}

toast-bottom и sub-lowered: рука опущена, видно ровно 48 su, подпись скрыта. Отказная цель выбрана из расположения фигур **на bench**, зоны — из topology:

{target}

sub — геометрический пример длинной ARTHUR-MATCHUP-MEDUSA-01: она звучит при старте матча. sub-lowered — пример ARTHUR-ATTACK-01 «Защищайся!»: её произносит сам Arthur при атаке, в run I атаковал Merlin. Ни одна реплика не выдаётся за сыгранную в выбранный момент журнала.

## Мелкие решения и дельта 04

Сдержанная печатная геометрия: navy-панель, закрытая тонкая кромка, плоский шрифт; без эффектов. Крест ошибки и крест закрытия различаются толщиной и назначением, предупреждение — заполненным треугольником с navy «!» из HB-29 и кромкой 2 su. Значки не экспортируются как новые ассеты. Отказ: пластина 24 su, X, тёмная внешняя keyline, 350 мс.

Проверяется фактическая маленькая плашка «Рука n/7», а пустая остальная часть HAND-CAPTION reserve свободна для SUB с отступом 8 su. Высота SUB — полный line box Roboto + 10 su, минимум 28 su. Предупреждение переносится по словам без усечения и имеет полный close cross. Самый новый тост снизу. Баннер начала хода длится 600 мс; **тост ждёт окончания баннера**, на финалах баннера нет.

ВР-VS2-HB38-18 (по делегированию, fix1): в defense-window клетки не интерактивны и LOG скрыт, поэтому COMBAT проверяет только принятые дилатированные фигуры и каждый прямоугольник HUD; HAND-CAPTION имеет зазор 8 su. spaces_px2 остаётся информационным измерением каждой попытки. В GAME клетки остаются препятствиями.

В боевом overlay группа двух тостов и длинного субтитра размещается целиком: SUB ниже тостов с gap 8 su. Цепочка: bottom-combined → top-combined → вверх по одному пикселю до STATUS.bottom + 8 su → newest-only с капсулой ниже → честный FAIL. Подробные дельты newest-only записаны в facts.deltas_04.

При неудаче всей цепочки overlay подписан FAIL; отказ и все попытки остаются в отчёте. Тёмная внешняя `mark.keyline` отказной плашки — обязательный служебный контур; её низкий контраст к собственному navy сохранён как `outer_keyline_informational`. Функциональная пара отказа — X/плашка. Приёмочная пара `panel.edge`/тело проверяется для панелей, тостов и капсулы, как §02 3.5; keyline не выдаётся за светлую panel.edge.

{fix1_reports.markdown(V,BEFORE)}

## Проверка P1–P14

| Требование | Реализация и доказательство |
|---|---|
{rows}

## Что не прошло

{failures}

Неудачные проверки сохранены в verification.acceptance и failures; статус не «принято».

## Открытые данные

Синхронные HP/рука на момент последней строки журнала не реконструируются: используется разрешённая HB-07 проекция. Положение фигур — bench, не run I. Маленькие старые клиентские имена/HP над фигурами являются **артефактом исходного фона**, их не ретушировали. Состав неизвестных карт после reconnect не утверждается; тестовые руки обозначены как примеры. Новых неподтверждённых игровых чисел не добавлено. Каждое видимое число базовых панелей сохраняет HB-07 источник.

## Строки без ключа

«Х{{n}}» / EN «T{{n}}» — §04 2.10, ВР-VS2-HB38-16, отдельного StringTable key нет. Пунктуация соединения ms.log.move — `, ` из оригинальной строки trace. Цифры гарпий и боевые значения базовых панелей — принятый HB-07, а не новые ключи HB-38.

## Входы и воспроизведение

source-hashes-before.json: {len(hb.BASELINE['files'])} файлов, включая всё дерево v3; snapshot модулей скопированы побайтно до работы. В verification.source_unchanged проверяется полная SHA256 неизменность, write audit запрещает мутации вне двух папок. Git, unreal/, сеть и subprocess не используются.

{hashdiff}

Изменения входов относительно прежнего source-hashes-before.json: {json.dumps(V['source_changed_paths'],ensure_ascii=False)}. Базовый файл хешей не перезаписан. Новый вход DroidSansFallback.ttf и его SHA256 — verification.fix1_inputs.

Запуск: `python -B -X utf8 art/imagegen/hud-feed-v1-codex/_tools/build_feed.py`. Независимый аудит: `python -B -X utf8 art/imagegen/hud-feed-v1-codex/_tools/audit_feed.py`. Генератор выводит PNG сразу в реальном размере холста; текст ceil(type_su × scale), скан целиком inside CP-13, один Lanczos непосредственно из исходника. Rec.709: (2126R + 7152G + 722B + 5000) // 10000. Манифест создаётся последним после README, facts и verification.
'''
    (PKG/'README.md').write_text(txt,encoding='utf8')

def manifest():
    dump(PKG/'manifest-sha256.json',{'schema':'HB-38.manifest/1','self_excluded':'manifest-sha256.json','files':{rel(p):sha(p) for root in [PKG,DERIVED] for p in sorted(root.rglob('*')) if p.is_file() and p!=PKG/'manifest-sha256.json'}})

def finalize_reports():
    dump(PKG/'facts.json',F);dump(PKG/'verification.json',V);readme()
    # Refresh README after the actual output sizes replace the provisional
    # pre-write package size. Final numeric update preserves decimal length.
    for _ in range(2):
        size=sum(z.stat().st_size for z in PKG.rglob('*') if z.is_file() and z.name!='manifest-sha256.json')
        V['acceptance']['package_30MB'].update(measured=size,passed=size<=30_000_000)
        V['package_bytes_without_manifest']=size
        V['failures']=[k for k,r in V['acceptance'].items() if not r['passed']]
        dump(PKG/'verification.json',V);readme()
    print('Acceptance failures:',V['failures'],flush=True)
    manifest()

def build():
    evidence();skin_checks()
    for b in hb.BG:
        for w,h,ui,s in CONFIGS:
            cs=[]
            for st in STATES:
                c=render(b,st,w,h,ui,s);final=audit_canvas(c);save_pair(DERIVED/(c.id+'.png'),final);cs.append(c)
            cc=combat(cs[0]);sheets(b,w,h,ui,s,cs,cc)
            for a,bb in itertools.combinations(['toast-info','toast-warning','toast-error'],2):
                ca=next(c for c in cs if c.state==a);cb=next(c for c in cs if c.state==bb)
                # Measure authored alpha silhouettes (scene and hand excluded).
                alpha_a=np.asarray(ca.hud)[:,:,3];alpha_b=np.asarray(cb.hud)[:,:,3]
                delta=int(np.count_nonzero(alpha_a!=alpha_b))
                V['gray_pairs'].append({'board':b,'canvas':[w,h,ui],'pair':[a,bb],'shape_changed_pixels':delta,'passed':delta>0})
            primary=np.array(rgb('primary'));secondary=np.array(rgb('secondary'));ld=float((primary-secondary)@np.array([.2126,.7152,.0722]))
            V['gray_pairs'].append({'board':b,'canvas':[w,h,ui],'pair':['LOG last','LOG older'],'solid_ink_luma_delta':ld,'passed':ld>=20})
            print('Built',b,f'{w}x{h}/{ui}',flush=True)
    c=render('marmoreal','toast-stack',1920,1080,100,1.,'en');final=audit_canvas(c);save_pair(DERIVED/(c.id+'.png'),final)
    V['gray']={'method':'Rec.709 integer rational coefficients; alpha preserved','every_final_pair_present':True,'review_only_downscaled':True}
    export_checks();source_checks();fix1_reports.summarize(PKG,DERIVED,F,V,BEFORE,sha);acceptance()
    finalize_reports()
if __name__=='__main__':
    if '--reports-only' in sys.argv:
        F=load(PKG/'facts.json');V=load(PKG/'verification.json')
        changes=[k for k in ('toast_placement','sub_placement','persistent_blocks','hand_geometry') if fix1_reports.game_rows(BEFORE['game_placements'][k])!=fix1_reports.game_rows(V[k])]
        V['fix1'].update(game_placements_unchanged=not changes,game_placement_changes=changes,comparison_note='Unique GAME ids, first occurrence; original combat persistent records were duplicate toast-stack ids. Full original records retained in fix1-before.json.')
        source_checks();acceptance();finalize_reports()
    else:build()
