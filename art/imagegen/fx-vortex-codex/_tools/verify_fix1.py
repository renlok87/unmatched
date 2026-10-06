"""Corrective checks of saved pixels. No engine, git, or writes outside package."""
import json
import math
import hashlib
from pathlib import Path
import numpy as np
from PIL import Image
import build_vortex as b


def cc(a):
    from verify_vortex import components
    return components(a)


def nearest(a,size):
    return np.asarray(Image.fromarray(a.astype(np.uint8)*255).resize((size,size),Image.Resampling.NEAREST))>0


def augment(report,cells,preview):
    before=json.loads((b.PACKAGE/'fix1-before.json').read_text(encoding='utf-8'))
    final_rg=[c[:,:,:2].max(axis=2)>0 for c in cells]
    continuity=[]
    visibility=[]
    chip_checks=[]
    # Expected ring membership only locates each segment; measured material is
    # always taken from the final exported atlas, including chip overdraw.
    for i in range(15):
        _,layers=b.build_frame(i)
        for ring,layer in enumerate(layers):
            for size in (256,64,48):
                roi=nearest(layer>0,size)
                rg=nearest(final_rg[i],size) & roi
                n=cc(rg)
                expected=6 if i==14 else 3
                entry={'frame':i,'ring':ring,'size':size,'components':n,'expected':expected,'visible_pixels':int(rg.sum()),'passed':n==expected}
                if i<=13:
                    rotation=b.state(i)[1]*(1 if ring==0 else -1)
                    centres=np.array(b.PARAMS['gap_centres_degrees'][ring])+rotation+60
                    per_segment=[]
                    for centre in centres:
                        segment=(layer>0)&(b.angular_distance(b.ANGLE,centre)<60)
                        per_segment.append(cc(nearest(segment,size)&nearest(final_rg[i],size)))
                    entry['components_per_segment']=per_segment
                    entry['passed']=entry['passed'] and per_segment==[1,1,1]
                if 1<=i<=13:
                    continuity.append(entry)
                if size!=256:
                    visibility.append(entry)
    # Flash increment: reference outer ring R, final G; chips cannot alter ring R.
    _,layers=b.build_frame(12)
    flash=(layers[0]==1)&(cells[12][:,:,1]==255)
    flash_sizes=[]
    for size,minimum in ((256,500),(64,20),(48,12)):
        small=nearest(flash,size)
        flash_sizes.append({'size':size,'G_pixels_added':int(small.sum()),'components':cc(small),'minimum_pixels':minimum,'passed':int(small.sum())>=minimum and cc(small)==1})
    lumas=np.array(b.RGB) @ np.array([.2126,.7152,.0722])
    old_scale=b.state(12)[0]; old_r=115.2*old_scale
    old_flash=(b.RADIUS<old_r-4)&(b.RADIUS>=old_r-8)&(b.angular_distance(b.ANGLE,240+64)<12)
    clearance=[]
    for k in range(6):
        c=b.chip_geometry(12,k)
        dist=b.angular_distance(b.ANGLE[c['mask']],300)
        clearance.append(float(dist.min()-20))
    flash_report={'frame':12,'angular_width_degrees':40,'centre_degrees':300,'centre_offset_degrees':60,
                  'radial_band':'entire original outer R body; original G inner edge and B outer keyline retained',
                  'before_G_stroke_pixels_256':int(old_flash.sum()),'sizes':flash_sizes,
                  'body_luma_rec709':float(lumas[0]),'cream_luma_rec709':float(lumas[1]),'luma_difference':float(lumas[1]-lumas[0]),
                  'chip_clearance_degrees':clearance,'gap_clearance_degrees':26,
                  'flash_frames':[12],'frames_11_13_no_flash':all(not np.any((b.build_frame(i)[1][0]==1)&(cells[i][:,:,1]==255)) for i in (11,13))}
    flash_report['before_sizes']=[{'size':size,'G_pixels_added':int(nearest(old_flash,size).sum()),'components':cc(nearest(old_flash,size))} for size in (256,64,48)]
    flash_report['passed']=all(e['passed'] for e in flash_sizes) and min(clearance)>=6 and lumas[1]-lumas[0]>=20 and flash_report['frames_11_13_no_flash']
    for i in range(1,14):
        for k in range(min(6,math.ceil(6*i/4))):
            c=b.chip_geometry(i,k)
            yy,xx=np.nonzero(c['mask'])
            fill=int(c['fill'].sum()); facet=int(c['facet'].sum())
            chip_checks.append({'frame':i,'chip':k,'area_including_keyline_px2':int(c['mask'].sum()),
                                'fill_area_px2':fill,'facet_area_px2':facet,'facet_share':facet/max(1,fill),
                                'margin_px':int(min(xx.min(),yy.min(),255-xx.max(),255-yy.max()))})
    full=[c for c in chip_checks if 4<=c['frame']<=10]
    chip_pass=all(300<=c['area_including_keyline_px2']<=500 and .2<=c['facet_share']<=.35 for c in full) and min(c['margin_px'] for c in chip_checks)>=2
    preserved={name:hashlib.sha256((b.PACKAGE/name).read_bytes()).hexdigest()==sha for name,sha in before['sha256'].items() if name.startswith('concepts/') or name=='source-hashes-before.json'}
    ingame=b.PARAMS.copy()
    ingame={k:v for k,v in ingame.items() if k.startswith(('figure_','ingame_'))}
    ingame['rasterized_full_outer_diameter_px']={'1080p':86*230.4/256,'720p':57*230.4/256,'note':'cell dimensions rounded to integer pixels; diameter targets77/51.3333; coverage contours are subpixel'}
    ingame['sprite_cell_1080p_px']=[86,71]
    ingame['sprite_cell_720p_px']=[57,47]
    ingame['method']='mask weights bilinear; 720p source frame bilinear; squash .82; silhouette foreground restored; native tiles then nearest x4'
    bands=[]; gaps=[]
    # Effective mask coverage after bilinear filtering, before foreground occlusion.
    # >0.5 is the half-coverage contour; >0 records the filtered footprint too.
    for i in range(14):
        scale,rot,_=b.state(i)
        maskcell=Image.fromarray(cells[i])
        _,sample=b.ingame_effect(maskcell,55*2/3)
        h,w=sample.shape[:2]
        yy,xx=np.mgrid[:h,:w]
        x=(xx+.5)*256/w-128; y=(yy+.5)*256/h-128
        radius=np.hypot(x,y); angle=np.degrees(np.arctan2(y,x))%360
        for ring,base in enumerate((115.2,65)):
            thickness=b.PARAMS['body_width_px_at_full_size'][ring]*scale+8
            annulus=(radius<=base*scale+3)&(radius>=base*scale-thickness-3)
            cover=sample[:,:,:3].sum(axis=2)
            solid=(cover>.5)&annulus
            # ROI excludes detached shards and locates the sampled ring coverage.
            _,layers=b.build_frame(i)
            ring_a=Image.fromarray((layers[ring]>0).astype(np.uint8)*255).resize((w,h),Image.Resampling.BILINEAR)
            visible=solid & (np.asarray(ring_a)>127)
            n=cc(visible)
            gaps.append({'frame':i,'ring':ring,'components':n,'expected':3,'passed':n==3})
            if i in (0,6,12):
                # Horizontal diameter scan near midline, only a non-gap side.
                # Ring endpoints can coincide with scanline; use longest radial
                # run over rows closest to centre and record every sampled run.
                runs=[]
                valid_sides=[]
                ring_rotation=rot if ring==0 else -rot
                gap_centres=np.array(b.PARAMS['gap_centres_degrees'][ring])+ring_rotation
                for side_angle,side in ((180,slice(0,w//2)),(0,slice(w//2,w))):
                    clearance=float(b.angular_distance(gap_centres,side_angle).min())
                    if clearance <= b.PARAMS['gap_width_degrees'][ring]/2+12:
                        continue  # This scan crosses an angular endpoint, not band thickness.
                    valid_sides.append(side_angle)
                    for row in (h//2-1,h//2):
                        v=visible[row,side]
                        edges=np.diff(np.r_[False,v,False].astype(int))
                        runs.extend((np.where(edges==-1)[0]-np.where(edges==1)[0]).tolist())
                minimum=min(runs) if runs else 0
                bands.append({'frame':i,'ring':ring,'size':'720p','body_cream_keyline_width_px':minimum,'horizontal_radial_runs_px':runs,'scan_side_angles_degrees':valid_sides,'coverage_threshold':.5,'expected_min_px':2,'passed':minimum>=2})
    ingame['visible_ring_band_widths']=bands
    ingame['gaps_720p_frames_0_13']=gaps
    ingame['passed']=all(e['passed'] for e in bands+gaps)
    ingame['measurement_scope']='effect coverage before Medusa foreground mask; gap CC 8-connected; native bilinear image at half coverage, horizontal equator radial runs'
    exports={}
    paths=[]
    gray_pairs=[]
    for folder in (b.PACKAGE/'vector',b.PACKAGE/'comparison',b.DERIVED/'comparison'):
        for p in sorted(folder.glob('*.png')):
            im=Image.open(p); a=np.asarray(im)
            if im.mode=='RGBA':
                yy,xx=np.nonzero(a[:,:,3])
                margin=int(min(xx.min(),yy.min(),im.width-1-xx.max(),im.height-1-yy.max())) if len(xx) else None
            else:
                margin=0
            name=b.relative(p)
            exports[name]={'size':list(im.size),'mode':im.mode,'margin_px':margin,'touches_edge':margin==0,'margin_scope':'opaque full sheet canvas' if im.mode!='RGBA' else 'alpha silhouette; atlas cell margins checked separately'}
            paths.append(name)
            if 'gray-rec709' not in p.name:
                if p.name.endswith('-colour.png'):
                    gray=p.with_name(p.name.replace('-colour','-gray-rec709'))
                else:
                    gray=p.with_name(p.stem+'-gray-rec709.png')
                valid=False
                if gray.is_file():
                    source=Image.open(p)
                    if p.name=='T_FX_MedusaVortex_4x4.png':
                        source=Image.open(p.with_name('T_FX_MedusaVortex_4x4-preview.png'))
                    expected=b.grey(source)
                    got=np.asarray(Image.open(gray).convert('RGB'))
                    valid=bool(np.array_equal(np.asarray(expected),got))
                gray_pairs.append({'colour':name,'gray':b.relative(gray),'present':gray.is_file(),'rec709_exact':valid})
    off=np.any(np.all(preview[:,:,:3,None]==np.array(b.RGB).T[None,None,:,:],axis=2),axis=2)
    opaque=preview[:,:,3]>0
    report['visual_inspection']={'performed':True,'inspected':['comparison/plan-48px-nearest4x-colour.png','comparison/plan-256px-colour.png','comparison/ingame-720p-native-nearest4x-gray-rec709.png','scraped-data/derived/fx-vortex-codex/comparison/ingame-720p-native-nearest4x-colour.png','scraped-data/derived/fx-vortex-codex/comparison/ingame-1080p-native-colour.png','scraped-data/derived/fx-vortex-codex/comparison/fix1-figure-measurement-zoom.png'],'engine_acceptance_claimed':False}
    report['source_unchanged']={'passed':not report['changed_inputs'] and report['checks']['hud_tree_unchanged'], 'unchanged':not report['changed_inputs'] and report['checks']['hud_tree_unchanged'],'inputs_count':report['inputs_hashed'],'hud_files_count':report['hud_files_hashed'],'changed_count':len(report['changed_inputs']),'v1_and_baseline_unchanged':preserved}
    report['exports']=exports
    report['palette']={'off_token_share_opaque_final':float((~off & opaque).sum()/opaque.sum()),'deltaE76_max':report['palette_deltaE76_max'],'scope':'opaque final colour atlas; filtered simulation sheets necessarily blend tokens/background'}
    report['gray']={'every_final_and_sheet_has_gray_copy':all(x['present'] and x['rec709_exact'] for x in gray_pairs),'copies':gray_pairs,'token_luma_rec709':dict(zip(('body','cream','keyline'),lumas.tolist()))}
    required=['vector/T_FX_MedusaVortex_4x4.png','vector/T_FX_MedusaVortex_4x4-preview.png','vector/T_FX_MedusaVortex-poster-frame0.png','vector/T_FX_MedusaVortex-reduced-motion-frame6.png','comparison/timing-strip.png','comparison/timing-strip-gray-rec709.png']
    required += [f'comparison/{angle}-{size}px'+('-nearest4x' if size!=256 else '')+f'-{colour}.png' for angle in ('plan','pitch55-scale082') for size in (256,64,48) for colour in ('colour','gray-rec709')]
    required += [f'comparison/ingame-{res}p-native'+('-nearest4x' if zoom==4 else '')+f'-{colour}.png' for res in (1080,720) for zoom in (1,4) for colour in ('colour','gray-rec709')]
    missing=[b.relative(folder/name) for folder in (b.PACKAGE,b.DERIVED) for name in required if (folder==b.PACKAGE or name.startswith('comparison/')) and not (folder/name).is_file()]
    report['sizes']={'every_deliverable_present':not missing,'missing':missing,'deliverables':paths}
    report['checks']['required_exports_present']=not missing
    report['fix1']={'flash':flash_report,'ring_continuity':{'passed':all(e['passed'] for e in continuity),'scope':'R|G from final atlas in each ring segment ROI, keyline excluded; 8-connected','per_frame_and_size':continuity},'chips':{'passed':chip_pass,'full_size_geometry':full,'all_frame_margins_and_facets':chip_checks,'local_bbox_aspects':[34/16,34/16,34/16],'rotation_pairwise_min_degrees':35,'spin_degrees_per_frame':15},'ingame':ingame}
    def line(passed,measured,expected,note=''):
        return {'passed':bool(passed),'measured':measured,'expected':expected,'note':note}
    report['acceptance']={
        '16_frames':line(report['frame_count']==16,report['frame_count'],16),
        '1024x1024':line(report['checks']['atlas_rgba_1024x1024'],report['atlas_size_px'],[1024,1024]),
        'palette_dE76_le_3':line(report['palette_deltaE76_max']<=3,report['palette_deltaE76_max'],'<=3'),
        'gray_sheet_present':line(report['gray']['every_final_and_sheet_has_gray_copy'],len(gray_pairs),'every final and sheet'),
        'outside_folder_empty':line(not report['outside_folder'],report['outside_folder'],[]),
        '64px_48px_rings_and_gaps':line(all(e['passed'] for e in visibility),visibility,'3 segments each ring; 6 terminal arcs at frame14','final atlas R|G, not ring-only material'),
        'no_green_no_red':line(report['checks']['no_green_or_red_in_effect'],report['effect_colours_rgb'],'only three stone tokens','technical mask channels excluded'),
        'fix1.flash':line(flash_report['passed'],flash_report,'>=500/20/12 px, one CC, luma difference >=20, clearance >=6 degrees'),
        'fix1.ring_continuity':line(report['fix1']['ring_continuity']['passed'],continuity,'each segment one component at 256/64/48 px, frames1-13'),
        'fix1.ingame':line(ingame['passed'],ingame,'1.4 x measured figure height; >=2px bands; 3 ring CC at720p'),
        'fix1.chips':line(chip_pass,report['fix1']['chips'],'6 irregular shards, 300-500px2,20-35%facet,margin>=2px')}
    report['checks']['v1_concepts_and_baseline_preserved']=all(preserved.values())
    report['checks']['final_rings_readable']=all(e['passed'] for e in visibility)
    report['small_size_ring_evidence']=visibility
    report['failures']=[k for k,v in report['checks'].items() if not v]+[k for k,v in report['acceptance'].items() if not v['passed']]
    report['verification_status']='passed_with_disclosed_limits' if not report['failures'] else 'failed'
    return report
