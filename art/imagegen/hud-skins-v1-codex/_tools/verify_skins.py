"""HB-08 fix1: delivered pixel, sheet, source, text and archive checks."""
import hashlib
import importlib.util
import itertools
import json
import re
import sys
from pathlib import Path
import numpy as np
from PIL import Image
sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[2]
spec = importlib.util.spec_from_file_location('hb08_renderer', HERE/'draw_skins.py')
renderer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(renderer)

def load(p):
    return json.loads(p.read_text(encoding='utf-8'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def linear(c):
    c = np.asarray(c,dtype=float)/255
    return np.where(c<=.04045,c/12.92,((c+.055)/1.055)**2.4)

def contrast(a,b):
    x,y = linear(a)@[.2126,.7152,.0722],linear(b)@[.2126,.7152,.0722]
    return float((max(x,y)+.05)/(min(x,y)+.05))

def lab(c):
    xyz = linear(c)@np.array([[.4124564,.2126729,.0193339],[.3575761,.7151522,.1191920],[.1804375,.0721750,.9503041]])
    xyz /= [.95047,1,1.08883]
    d = 6/29
    f = np.where(xyz>d**3,np.cbrt(xyz),xyz/(3*d*d)+4/29)
    return np.stack((116*f[...,1]-16,500*(f[...,0]-f[...,1]),200*(f[...,1]-f[...,2])),axis=-1)

def neighbors(m):
    out = np.zeros_like(m)
    h,w = m.shape
    for dy in (-1,0,1):
        for dx in (-1,0,1):
            out[max(0,dy):min(h,h+dy),max(0,dx):min(w,w+dx)] |= m[max(0,-dy):min(h,h-dy),max(0,-dx):min(w,w-dx)]
    return out

def palette_check(im,allowed):
    a = np.array(im.convert('RGBA'))
    colors,ix = np.unique(a[:,:,:3].reshape(-1,3),axis=0,return_inverse=True)
    dist = np.linalg.norm(lab(colors)[:,None,:]-lab(allowed)[None,:,:],axis=2).min(axis=1)
    good = (dist<=3)[ix].reshape(a.shape[:2])
    opaque = a[:,:,3]==255
    aa = opaque & ~good & neighbors(good & (a[:,:,3]>0))
    bad = opaque & ~good & ~aa
    return {'passed':not bool(bad.any()),'opaque_pixels':int(opaque.sum()),'excluded_edge_antialias_pixels':int(aa.sum()),'opaque_outside_deltaE76_3':int(bad.sum())}

def components(m,diagonal=False):
    todo = set(map(tuple,np.argwhere(m)))
    count = 0
    offsets = list(itertools.product((-1,0,1),repeat=2)) if diagonal else [(-1,0),(1,0),(0,-1),(0,1)]
    while todo:
        count += 1
        stack = [todo.pop()]
        while stack:
            y,x = stack.pop()
            for dy,dx in offsets:
                q = (y+dy,x+dx)
                if q in todo:
                    todo.remove(q)
                    stack.append(q)
    return count

def masks(w,h,r,t):
    outer = renderer.rect_mask(w,h,1,1,w-2,h-2,r)
    inner = renderer.rect_mask(w,h,1+t,1+t,w-2-2*t,h-2-2*t,r-t)
    return outer,inner,np.clip(outer-inner,0,1)

def over_rgba(body,alpha,edge,opacity):
    b = Image.new('RGBA',(1,1),tuple(int(v) for v in body)+(round(alpha*255),))
    e = Image.new('RGBA',(1,1),tuple(int(v) for v in edge)+(round(opacity*255),))
    return list(Image.alpha_composite(b,e).getpixel((0,0)))

def verify():
    manifest = load(PACKAGE/'manifest.json')
    margins = load(PACKAGE/'slice-margins.json')['files']
    before = load(PACKAGE/'source-hashes-before.json')['files']
    after = {p:sha(ROOT/p) if (ROOT/p).is_file() else None for p in before}
    changed = [p for p in before if before[p]!=after[p]]
    added = sorted({p.relative_to(ROOT).as_posix() for p in (ROOT/'art/imagegen/hud-icons-v3').rglob('*') if p.is_file()}-set(before))
    provenance = load(PACKAGE/'fix1-provenance.json')
    snapshot_ok = sha(HERE/'draw_icons_v3_snapshot.py')==before['art/imagegen/hud-icons-v3/_tools/draw_icons.py']
    derived = [{'hex':'#F3C55B','formula':'round(0.92 * #F2C14E + 0.08 * #FAF8F2)'},{'hex':'#D5AA45','formula':'round(0.88 * #F2C14E)'},{'hex':'#4E5457','formula':'round(0.4 * #B9B2A6 + 0.6 * #061623), opaque bake'}]
    allowed = [renderer.rgb(k) for k in renderer.TOKENS]
    combos = {(renderer.style(n)['body'],renderer.style(n)['body_opacity'],renderer.style(n)['edge'],renderer.style(n)['edge_opacity']) for n in renderer.NAMES if not n.endswith('_Focus')}
    for body,alpha,edge,opacity in sorted(combos|{('card.navy',.92,'card.cream',.16)}):
        if opacity<1:
            rgba = over_rgba(renderer.rgb(body),alpha,renderer.rgb(edge),opacity)
            allowed.append(rgba[:3])
            derived.append({'hex':'#'+''.join(f'{v:02X}' for v in rgba[:3]),'rgba':rgba,'formula':f'Porter-Duff OVER: {edge} at round({opacity}*255)/255 over {body} at round({alpha}*255)/255; straight RGB = (Ce*ae + Cb*ab*(1-ae))/(ae+ab*(1-ae))'})
    exports,skins,image_sets,meta_sets,palette_results = {},{},{},{},{}
    corners_ok = profiles_ok = closed_ok = focus_ok = checkbox_ok = True
    for scale in (1,2,4):
        directory = f'vector/x{scale}' if scale<4 else 'masters'
        images = {n:Image.open(PACKAGE/directory/f'T_Skin_{n}.png').convert('RGBA') for n in renderer.NAMES}
        metas = {n:manifest['skins'][f'{directory}/T_Skin_{n}.png'] for n in renderer.NAMES}
        image_sets[scale],meta_sets[scale] = images,metas
        for name,im in images.items():
            key = f'{directory}/T_Skin_{name}.png'
            m,arr = metas[name],np.array(im)
            t,rad = m['edge_px'],m['radius_su']*scale
            outer,inner,edge = masks(im.width,im.height,rad,t)
            if m['focus_overlay']:
                actual_loop,pixel_match = arr[:,:,3]>25,True
            else:
                st = m['style']
                expected = over_rgba(renderer.rgb(st['body']),st['body_opacity'],renderer.rgb(st['edge']),st['edge_opacity'])
                pixel_match = bool(np.all(arr[edge==1]==expected))
                if name=='Input_Error':
                    # Preserve the accepted small X over the unbroken normal edge.
                    # Validate its complete overlay, rather than mistaking red ink
                    # covering cream for a missing edge pixel.
                    def cross(ctx):
                        ctx.set_line_width(scale)
                        cx,cy,half = im.width-3*scale-1,1+3*scale,1.5*scale
                        for sign in (-1,1):
                            ctx.move_to(cx-half,cy-sign*half)
                            ctx.line_to(cx+half,cy+sign*half)
                        ctx.stroke()
                    sign_image = renderer.merge_layers([(renderer.mask(im.width,im.height,cross),'state.error',1.)])
                    expected_image = Image.alpha_composite(images['Input_Normal'],sign_image)
                    pixel_match = bool(np.array_equal(arr,np.array(expected_image)))
                actual_loop = (edge>.1) & (np.max(abs(arr[:,:,:3].astype(float)-renderer.rgb(st['body'])),axis=2)>1)
            topology = components(actual_loop,True)==1 and components(~actual_loop)==2
            closed_ok &= topology and pixel_match
            stretched = []
            for target in renderer.working_sizes(name):
                if m['stretch']=='none':
                    a = np.array(renderer.display(name,scale,target,images,metas))
                    native = im.size==(24*scale+2,24*scale+2) and np.array_equal(a,arr)
                    checkbox_ok &= native and all(margins[key][k]==im.size[0 if k in ('left','right') else 1] for k in ('left','top','right','bottom'))
                    stretched.append({'target_su':list(target),'native_byte_identical':native})
                    continue
                extra = 8*scale if m['focus_overlay'] else 0
                size = (target[0]*scale+2+extra,target[1]*scale+2+extra)
                a = np.array(renderer.nine_slice(im,m['slice_px'],size))
                l,tt,r,b = (m['slice_px'][k] for k in ('left','top','right','bottom'))
                corners = all((np.array_equal(a[:tt,:l],arr[:tt,:l]),np.array_equal(a[:tt,-r:],arr[:tt,-r:]),np.array_equal(a[-b:,:l],arr[-b:,:l]),np.array_equal(a[-b:,-r:],arr[-b:,-r:])))
                band = t+1
                profiles = all((np.array_equal(a[:band,a.shape[1]//2],arr[:band,im.width//2]),np.array_equal(a[-band:,a.shape[1]//2],arr[-band:,im.width//2]),np.array_equal(a[a.shape[0]//2,:band],arr[im.height//2,:band]),np.array_equal(a[a.shape[0]//2,-band:],arr[im.height//2,-band:])))
                corners_ok &= corners
                profiles_ok &= profiles
                if m['focus_overlay']:
                    col = a[:,a.shape[1]//2,3]
                    focus_ok &= bool(np.all(col[1:1+2*scale]==255) and np.all(col[1+2*scale:1+4*scale]==0) and np.all(a[rad+1:-rad-1,rad+1:-rad-1,3]==0))
                stretched.append({'target_su':list(target),'output_px':list(size),'corners_byte_identical':corners,'edge_profiles_byte_identical':profiles})
            pal = palette_check(im,np.array(allowed))
            palette_results[key] = pal
            skins[key] = {'closed_outline':topology,'expected_edge_pixels_match':pixel_match,'stretch':stretched,'palette':pal,'slice_formula_pass':m['stretch']=='none' or all(v==rad+t+1 for v in m['slice_px'].values()),'hash_matches':sha(PACKAGE/key)==m['sha256']}
    pairs = []
    for scale in (1,2):
        for group,page in ((renderer.NAMES[3:9],2),(renderer.NAMES[9:14],3)):
            for target in ((120,32),(180,40),(240,48)):
                width,height = target[0]*scale+2,target[1]*scale+2
                canvas = (width+8*scale,height+8*scale)
                _,inn,loop = masks(width,height,4*scale,scale)
                bodymask = np.zeros(canvas[::-1],dtype=bool)
                edgemask = np.zeros_like(bodymask)
                bodymask[4*scale:4*scale+height,4*scale:4*scale+width] = inn==1
                edgemask[4*scale:4*scale+height,4*scale:4*scale+width] = loop>=.5
                _,_,focusloop = masks(*canvas,8*scale,2*scale)
                for bg in ('navy','marmoreal','sarpedon'):
                    info = next(s for s in manifest['sheets'] if s['background']==bg and s['scale']==scale and s['page']==page and s['mode']=='gray')
                    with Image.open(ROOT/info['path']) as sheet:
                        values = {}
                        for n in group:
                            p = next(p for p in info['placements'] if p['name']==n and tuple(p['target_su'])==target)
                            x,y = p['normal_origin_px']
                            values[n] = np.array(sheet.crop((x-4*scale,y-4*scale,x-4*scale+canvas[0],y-4*scale+canvas[1])))[:,:,0].astype(float)
                    for a,b in itertools.combinations(group,2):
                        diff = abs(values[a]-values[b])
                        bd,ed = float(np.median(diff[bodymask])),float(np.median(diff[edgemask]))
                        fd = float(np.median(diff[focusloop>=.5])) if a.endswith('_Focus') or b.endswith('_Focus') else None
                        passed = bd>=20 or ed>=20 or (fd is not None and fd>=20)
                        pairs.append({'a':a,'b':b,'scale':scale,'background':bg,'size_su':list(target),'median_body_luma_delta':bd,'median_closed_edge_luma_delta':ed,'median_focus_ring_luma_delta':fd,'passed':passed})
    sheets = []
    catalog_items = [{'path':(PACKAGE/f'comparison/catalog-{mode}.png').relative_to(ROOT).as_posix(),'mode':mode,'sha256':sha(PACKAGE/f'comparison/catalog-{mode}.png')} for mode in ('color','gray')]
    for s in manifest['sheets']+catalog_items:
        p = ROOT/s['path']
        check = {'path':s['path'],'hash_matches':sha(p)==s['sha256']}
        if s['mode']=='gray':
            c = np.array(Image.open(ROOT/s['path'].replace('-gray.png','-color.png')).convert('RGB'),dtype=float)
            g = np.array(Image.open(p).convert('RGB'))
            check['rec709_byte_exact'] = bool(np.all(g==np.rint(c@[.2126,.7152,.0722]).astype(np.uint8)[:,:,None]))
        sheets.append(check)
    for root in (PACKAGE,renderer.DERIVED):
        for p in sorted(root.rglob('*.png')):
            with Image.open(p) as im:
                arr = np.array(im.convert('RGBA'))
                ys,xs = np.where(arr[:,:,3]>0)
                margin = {'left':int(xs.min()),'top':int(ys.min()),'right':im.width-1-int(xs.max()),'bottom':im.height-1-int(ys.max())} if len(xs) else dict.fromkeys(('left','top','right','bottom'),min(im.size))
                rel = p.relative_to(PACKAGE).as_posix() if root==PACKAGE else ''
                if rel.startswith('concepts/'):
                    rel = '/'.join(Path(rel).parts[2:])
                exports[p.relative_to(ROOT).as_posix()] = {'size_px':list(im.size),'mode':im.mode,'margin_px':margin,'touches_edge':min(margin.values())==0,'slice_px':{k:v for k,v in margins.get(rel,dict.fromkeys(('left','top','right','bottom'),0)).items() if k!='stretch'},'slice_applicable':rel in margins,'stretch':margins.get(rel,{}).get('stretch','none'),'role':'skin' if rel in margins else 'background_or_comparison_or_fixed_layer'}
                if root==PACKAGE and p.parent.parent.name=='layers':
                    palette_results[p.relative_to(PACKAGE).as_posix()] = palette_check(im,np.array(allowed))
    navy = renderer.rgb('card.navy')
    primary = []
    for n in renderer.NAMES[9:14]:
        base = 'BtnPrimary_Normal' if n.endswith('_Focus') else n
        text = 'text.primary' if base.endswith('_Disabled') else 'card.navy'
        ratio = contrast(renderer.rgb(text),renderer.rgb(renderer.style(base)['body']))
        primary.append({'state':n,'text':renderer.TOKENS[text],'body':renderer.TOKENS[renderer.style(base)['body']],'ratio':round(ratio,4),'passed':ratio>=4.5})
    edges = []
    for n in renderer.NAMES[3:14]:
        st = renderer.style(n)
        if n.endswith('_Focus'):
            edge = renderer.rgb('card.glyph')
            body = renderer.rgb('turn.flash.yellow') if n.startswith('BtnPrimary') else navy
        else:
            rgba = over_rgba(renderer.rgb(st['body']),st['body_opacity'],renderer.rgb(st['edge']),st['edge_opacity'])
            edge = np.array(rgba[:3])*(rgba[3]/255)+navy*(1-rgba[3]/255)
            body = renderer.rgb(st['body'])
        ratio = contrast(edge,navy)
        disabled = n.endswith('_Disabled')
        edges.append({'state':n,'to_panel_bg':round(ratio,4),'to_own_body':round(contrast(edge,body),4),'disabled_exempt':disabled,'passed_literal_panel_bg':disabled or ratio>=3})
    records = load(PACKAGE/'generation-records.json')
    generation_ok = all(sha(ROOT/r['output'])==r['sha256']==sha(ROOT/r['unretouched']) for r in records['records'])
    links,encoding = [],{}
    for root in (PACKAGE,renderer.DERIVED):
        for p in sorted(root.rglob('*')):
            if p.suffix not in ('.md','.json'):
                continue
            value = p.read_text(encoding='utf-8')
            if p.suffix=='.json':
                json.loads(value)
            encoding[p.relative_to(ROOT).as_posix()] = {'cyrillic_characters':len(re.findall('[\u0400-\u04ff]',value)),'double_question_runs':len(re.findall(r'\?{2,}',value)),'utf8_valid':True}
            if p.suffix=='.md':
                for label,target in re.findall(r'\[([^\]]+)\]\(([^)]+)\)',value):
                    if not re.match(r'^\w+://',target):
                        links.append({'file':p.relative_to(ROOT).as_posix(),'target':target,'resolves':(p.parent/target.split('#')[0]).exists()})
    review = (HERE/'claude-review-verbatim.md').read_bytes()
    review_ok = (PACKAGE/'README.md').read_bytes().endswith(review) and hashlib.sha256(review).hexdigest()==provenance['claude_review_sha256']
    bad = sum(v['opaque_outside_deltaE76_3'] for v in palette_results.values())
    failed_pairs = [v for v in pairs if not v['passed']]
    forbidden = [p.relative_to(ROOT).as_posix() for root in (PACKAGE,renderer.DERIVED) for p in root.rglob('*') if 'cursor' in p.name.lower()]
    required = all({p.stem for p in (PACKAGE/f'vector/x{s}').glob('*.png')}=={'T_Skin_'+n for n in renderer.NAMES} for s in (1,2))
    acceptance = {}
    def clause(key,passed,measured,expected,note=''):
        acceptance[key] = {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    clause('palette',bad==0,bad,'0 opaque pixels outside deltaE76 <= 3; edge AA excluded')
    margins_match = all({k:v for k,v in margins[key].items() if k!='stretch'}==m['slice_px'] and margins[key]['stretch']==m['stretch'] for key,m in manifest['skins'].items())
    clause('slice_margins',len(margins)==87 and margins_match and all(v['slice_formula_pass'] for v in skins.values()),len(margins),'87 files; radius+edge+1px; fixed-checkbox full-image margins')
    clause('edge_not_stretched',corners_ok and profiles_ok,{'corners':corners_ok,'profiles':profiles_ok},'Byte-identical corners and transverse profiles at all 3 sizes')
    clause('focus_ring',focus_ok,{'ring_su':2,'gap_su':2},'Ring-only PNG, 2 su ring, 2 su gap')
    clause('button_gray_pairs',not failed_pairs,{'total':len(pairs),'failed':len(failed_pairs)},'All 450 comparisons: median body OR closed edge >=20; focus by full ring')
    clause('closed_outline',closed_ok,closed_ok,'One continuous constant-width rounded edge; no gaps or notches')
    clause('enabled_edge_contrast_to_panel_bg',all(v['passed_literal_panel_bg'] for v in edges),edges,'>=3:1 in every enabled state','Disabled edge intentionally dimmed; inactive controls exempt per task WCAG 1.4.11. Exact primary-normal navy edge is 1:1 to navy panel but 10.91:1 to yellow body: literal panel.bg clause conflicts with binding state table; colors preserved.')
    clause('primary_text_contrast',all(v['passed'] for v in primary),primary,'>=4.5:1 for all 5 states including disabled')
    clause('scope_excludes_pointer_assets',not forbidden,forbidden,'No pointer files; IC-58...IC-61 are a separate task')
    clause('required_exports',required,58,'29 exact skin names at x1 and x2; direct vector rasterization')
    clause('checkbox_native',checkbox_ok,{'content_su':24,'x1_px':26,'x2_px':50},'Fixed 24 su; no stretch; shown once per scale')
    clause('source_unchanged',not changed and not added and snapshot_ok and provenance['skins_geometry_unaffected'],{'changed':changed,'added':added,'snapshot_identical':snapshot_ok},'Input hashes unchanged; current v3 snapshot identical; skins geometry unaffected')
    clause('generation_pruned',generation_ok and len({r['run'] for r in records['records']})==1 and not (renderer.DERIVED/'concepts').exists(),{'records':len(records['records']),'archived_skins':87},'Only final run; concepts only vector/masters; derived only backgrounds/comparison')
    clause('gray_sheets',all(v.get('rec709_byte_exact',True) and v['hash_matches'] for v in sheets),len(sheets),'108 stretch sheets + 2 catalogs; byte-exact Rec.709 gray')
    clause('png_mode_and_skin_margin',all(v['mode']=='RGBA' and (not v['slice_applicable'] or (not v['touches_edge'] and min(v['margin_px'].values())==1)) for v in exports.values()),{'png_count':len(exports)},'Every PNG RGBA; every skin has 1px transparent field and does not touch edge')
    clause('artwork_hashes',all(v['hash_matches'] for v in skins.values()),len(skins),'All 87 output hashes match manifest')
    clause('utf8',all(v['double_question_runs']==0 for v in encoding.values()) and all(encoding[(PACKAGE/n).relative_to(ROOT).as_posix()]['cyrillic_characters']>0 for n in ('README.md','DESIGN.md','visual-review.json')),{'files':len(encoding)},'UTF-8; Cyrillic in Russian files; zero double-question runs')
    clause('links_and_review',all(v['resolves'] for v in links) and review_ok,{'links':len(links),'review_verbatim':review_ok},'Relative links resolve; Claude section verbatim at end')
    report = {'task':'HB-08','run':'CX-02r','status':'предложено','source_unchanged':not changed and not added,'exports':exports,'palette':{'derived':derived,'tokens':renderer.TOKENS,'opaque_outside_deltaE76_3':bad,'files':palette_results},'gray':{'method':'Median absolute difference of delivered Rec.709 encoded-sRGB gray; full body/full closed edge masks; full focus ring','pairs':pairs,'failed_pairs':failed_pairs,'sheets':sheets},'sizes':{'required_skin_png':58,'masters':29,'required_present':required,'working_sizes_su':manifest['working_sizes_su']},'outside_folder':[],'acceptance':acceptance,'text_encoding':encoding,'acceptance_pass':all(v['passed'] for v in acceptance.values()),'skins':skins,'contrast':{'primary_text':primary,'edges':edges,'disabled_edge_exemption':'Inactive control: dimmed edge intentional, exempt per task WCAG 1.4.11.'},'source_hashes_after':after,'source_changes':changed,'source_tree_added_files':added,'engine_provenance':provenance,'generation':{'passed':generation_ok,'last_run':manifest['last_run'],'pruned_runs':records['pruned_runs']},'relative_links':links,'limits':[{'id':'literal-edge-panel-bg','status':'unmet','detail':'Primary normal navy edge equals navy panel. Against its own yellow body: 10.91:1. Exact state table preserved.'},{'id':'reference-marmoreal','status':'historical-input-mismatch','detail':'Mandated crop contains volumetric surroundings and fighter labels; comparison context, not evidence of current game scene.'},{'id':'runtime','status':'outside-task','detail':'No Unreal runtime opened or built; separate runtime text contrast is analytical.'}]}
    renderer.dump(PACKAGE/'verification.json',report)
    # Scan AFTER the last content write, including this report itself.
    for root in (PACKAGE,renderer.DERIVED):
        for p in root.rglob('*'):
            if p.suffix in ('.md','.json'):
                value = p.read_text(encoding='utf-8')
                if p.suffix=='.json':
                    json.loads(value)
                encoding[p.relative_to(ROOT).as_posix()] = {'cyrillic_characters':len(re.findall('[\u0400-\u04ff]',value)),'double_question_runs':len(re.findall(r'\?{2,}',value)),'utf8_valid':True}
    renderer.dump(PACKAGE/'verification.json',report)
    print(json.dumps({'failed_acceptance':[k for k,v in acceptance.items() if not v['passed']],'palette_bad_pixels':bad,'gray_pairs':len(pairs),'failed_gray_pairs':len(failed_pairs),'primary_text':primary,'source_changes':changed},ensure_ascii=False,indent=2))

if __name__=='__main__':
    verify()
